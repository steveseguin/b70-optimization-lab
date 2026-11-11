// How much would a persistent ("megakernel") form win for a decode step's dense weight chain? (strategy S1,
// notes/2026-11-11-dsv41-speed-strategy.md). One card. A chain of L layers x 6 dependent Q8_0 matrix-vector
// stages at a 12-head card's shapes (q_a + kv 1792 x 5120, q_b 6144 x 1280, output-a 768 x 4096, output-b
// 864 x 8192, shared gate + up 768 x 5120, shared down 864 x 2304; distinct weights per layer, 35 MB per layer),
// stage g reading the vector stage g - 1 wrote (ping-pong buffers). Every row is GemvQ8P::row (the engine's code),
// so every form must give the same outputs bit for bit.
//   A   one launch per stage (the engine's form: 16 rows per 512-item work-group), back to back
//   P0  one persistent launch: G work-groups loop over the stages; after its rows of stage g a work-group adds to
//       stage g's counter (release, device scope); before stage g + 1 it waits for the counter to reach G (acquire)
//   P1  P0, and while waiting each sub-group first reads its rows of the next stage once (weights into the cache
//       before the input is ready)
//   P2  P0, and while waiting each sub-group reads only its FIRST row of the next stage
//   P3  persistent, sync per sub-group (each sub-group adds to the stage counter after its rows; the target is every
//       sub-group of the launch; each sub-group waits on its own, no work-group barrier), and BEFORE waiting it
//       loads its first row of the next stage into registers (RowPre: GemvQ8P::row split into the loads and the
//       same products in the same order), so the weight reads overlap the wait
//   P4  P3 without the early loads (the sync change alone)
//   Q   one launch per stage as A (one row per sub-group), but on an OUT-OF-ORDER queue with no dependencies, so no
//       barrier between launches: each kernel loads its row's first words into registers, waits until every
//       sub-group of the previous stage's launch has added to its counter, computes, adds to its own counter
//       (emulates CUDA's programmatic dependent launch; strategy idea #2 of the external survey). Relies on the
//       hardware dispatching the launches' work-groups in order (a later launch's spinning groups must not take
//       the slots an earlier launch still needs); a wait gives up after 2^20 polls (error flag, no hang).
//   Qi  Q's kernels on the in-order queue (the cost of the extra loads / counters without any overlap)
//   F   the floor: one launch reading the chain's weight bytes (no dependency), GB/s
// G = the work-group count of the persistent forms (512 items each); waits give up after 2^20 polls (well under a second) (an error
// flag, never a hang). Timing: forms interleaved, back to back; one chain = L layers.
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_persist_chain.cpp -o $S/bench_persist_chain
//   ONEAPI_DEVICE_SELECTOR=level_zero:N $S/bench_persist_chain [G]
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

static constexpr int NST = 6, L = 16;
static constexpr unsigned SR[NST] = {1792, 6144, 768, 864, 768, 864};
static constexpr unsigned SC[NST] = {160, 40, 128, 256, 160, 72}; // 32-weight chunks per row
static constexpr size_t rbytes(unsigned c) { return ((size_t)c * 34 + 15) & ~(size_t)15; }
static constexpr size_t BUF = 8192; // floats per ping-pong buffer (>= every stage's input and output)

static double ev_us(const sycl::event &a, const sycl::event &b) {
    return (b.get_profiling_info<sycl::info::event_profiling::command_end>() -
            a.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}

struct Chain {
    const uint8_t *w[L][NST];
    float *buf0, *buf1;
    unsigned *cnt; // L * NST counters
    unsigned *err;
};

template <unsigned C>
[[gnu::always_inline]] inline void rows_of(sycl::sub_group sg, unsigned lane, unsigned gsg, unsigned nsg, unsigned R,
                                           const uint8_t *w, const float *x, float *y) {
    const GemvQ8P<C, ActF32> k{R, 0};
    for (unsigned r = gsg; r < R; r += nsg) k.row(sg, lane, r, w, x, y);
}
// read rows of a stage once (P1: all of this sub-group's rows; P2: the first), into a dummy sum
[[gnu::always_inline]] inline uint32_t touch(sycl::sub_group sg, unsigned gsg, unsigned nsg, unsigned R, size_t rb,
                                             const uint8_t *w, bool first_only) {
    uint32_t acc = 0;
    for (unsigned r = gsg; r < R; r += nsg) {
        const uint32_t *p = reinterpret_cast<const uint32_t *>(w + (size_t)r * rb);
        for (size_t o = 0; o + 128 <= rb; o += 128) acc += sg_bload(sg, p + o / 4);
        if (first_only) break;
    }
    return acc;
}

// GemvQ8P<C>::row split in two: load() reads the row's scales and quant words into registers, dot() forms the same
// products in the same order (sycl_v41.hpp GemvQ8P::row) and stores y[r]
template <unsigned C> struct RowPre {
    static constexpr unsigned NQ = C / 4, SEGQ = Q8Seg<C>::v, ND = (C + 31) / 32;
    // the first PRE quant words are loaded early (whole segments, at most 16 words: more spills)
    static constexpr unsigned PRE = (16 / SEGQ) * SEGQ < NQ ? (16 / SEGQ) * SEGQ : NQ;
    static constexpr size_t RB = ((size_t)C * 34 + 15) & ~(size_t)15;
    float dv[ND];
    uint32_t q[PRE > 0 ? PRE : 1];
    const uint32_t *qw = nullptr;
    [[gnu::always_inline]] inline void load(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w) {
        const uint8_t *row = w + (size_t)r * RB;
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)C * 32);
#pragma unroll
        for (unsigned k = 0; k < ND; ++k) dv[k] = 32 * k + lane < C ? iq3::half(dp[32 * k + lane]) : 0.0f;
        qw = reinterpret_cast<const uint32_t *>(row);
#pragma unroll
        for (unsigned m = 0; m < PRE; ++m) q[m] = sg_bload(sg, qw + (size_t)m * 32);
    }
    [[gnu::always_inline]] inline void dot(sycl::sub_group sg, unsigned lane, unsigned r, const float *x, float *y) const {
        float sum = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NQ; s0 += SEGQ) {
            uint32_t qs[SEGQ];
#pragma unroll
            for (unsigned m = 0; m < SEGQ; ++m) qs[m] = s0 + m < PRE ? q[s0 + m] : sg_bload(sg, qw + (size_t)(s0 + m) * 32);
#pragma unroll
            for (unsigned m = 0; m < SEGQ; ++m) {
                const auto xv = sg_bloadN<4>(sg, x + (size_t)(s0 + m) * 128);
#pragma unroll
                for (unsigned k = 0; k < 4; ++k) {
                    const unsigned c = (s0 + m) * 4 + k;
                    const float d = sycl::select_from_group(sg, dv[c / 32], c % 32);
                    const float e = d * float(int8_t(uint8_t(qs[m] >> (8 * k))));
                    sum = sum + e * xv[k];
                }
            }
        }
        sum = sg_tree32(sg, sum);
        if (lane == 0) y[r] = sum;
    }
};
// one stage for P3 / P4: the first row from registers when preloaded, the others by GemvQ8P::row
template <unsigned C>
[[gnu::always_inline]] inline void rows_pre(sycl::sub_group sg, unsigned lane, unsigned gsg, unsigned nsg, unsigned R,
                                            const uint8_t *w, const float *x, float *y, const RowPre<C> &pre, bool have) {
    const GemvQ8P<C, ActF32> k{R, 0};
    unsigned r = gsg;
    if (have && r < R) {
        pre.dot(sg, lane, r, x, y);
        r += nsg;
    }
    for (; r < R; r += nsg) k.row(sg, lane, r, w, x, y);
}

template <int MODE> struct PersistS {
    Chain ch;
    unsigned G;
    template <unsigned C>
    [[gnu::always_inline]] inline void stage(sycl::sub_group sg, unsigned lane, unsigned gsg, unsigned nsg, int g, unsigned R,
                                             const uint8_t *w, const float *x, float *y) const {
        RowPre<C> pre;
        const bool have = MODE == 3 && gsg < R;
        if (have) pre.load(sg, lane, gsg, w); // the weights before the input is ready
        if (g > 0) {
            if (lane == 0) {
                sycl::atomic_ref<unsigned, sycl::memory_order::acq_rel, sycl::memory_scope::device,
                                 sycl::access::address_space::global_space>
                    a(ch.cnt[g - 1]);
                sycl::atomic_ref<unsigned, sycl::memory_order::relaxed, sycl::memory_scope::device,
                                 sycl::access::address_space::global_space>
                    ea(ch.err[0]);
                unsigned n = 0;
                while (a.load(sycl::memory_order::acquire) < nsg) {
                    if ((++n & 1023u) == 0 && ea.load() != 0) break;
                    if (n > (1u << 20)) {
                        ea.store(1u);
                        break;
                    }
                }
            }
            sycl::group_barrier(sg);
        }
        rows_pre<C>(sg, lane, gsg, nsg, R, w, x, y, pre, have);
        sycl::group_barrier(sg);
        if (lane == 0) { // only lane 0 stores outputs: its release covers them
            sycl::atomic_ref<unsigned, sycl::memory_order::acq_rel, sycl::memory_scope::device,
                             sycl::access::address_space::global_space>
                a(ch.cnt[g]);
            a.fetch_add(1u, sycl::memory_order::release);
        }
    }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const unsigned nsgw = it.get_local_range(0) / 32;
        const unsigned gsg = it.get_group_linear_id() * nsgw + sg.get_group_linear_id(), nsg = G * nsgw;
        for (int l = 0; l < L; ++l)
            for (int k = 0; k < NST; ++k) {
                const int g = l * NST + k;
                const float *x = (g & 1) ? ch.buf1 : ch.buf0;
                float *y = (g & 1) ? ch.buf0 : ch.buf1;
                switch (k) {
                case 0: stage<SC[0]>(sg, lane, gsg, nsg, g, SR[0], ch.w[l][0], x, y); break;
                case 1: stage<SC[1]>(sg, lane, gsg, nsg, g, SR[1], ch.w[l][1], x, y); break;
                case 2: stage<SC[2]>(sg, lane, gsg, nsg, g, SR[2], ch.w[l][2], x, y); break;
                case 3: stage<SC[3]>(sg, lane, gsg, nsg, g, SR[3], ch.w[l][3], x, y); break;
                case 4: stage<SC[4]>(sg, lane, gsg, nsg, g, SR[4], ch.w[l][4], x, y); break;
                default: stage<SC[5]>(sg, lane, gsg, nsg, g, SR[5], ch.w[l][5], x, y); break;
                }
            }
    }
};

// Q / Qi: stage g's launch, one row per sub-group; prev = sub-groups in stage g - 1's launch
template <unsigned C> struct QStage {
    const uint8_t *w;
    const float *x;
    float *y;
    unsigned R, prev;
    int g;
    unsigned *cnt, *err;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const unsigned r = packed_row_id(it);
        RowPre<C> pre;
        if (r < R) pre.load(sg, lane, r, w);
        if (g > 0) {
            if (lane == 0) {
                sycl::atomic_ref<unsigned, sycl::memory_order::acq_rel, sycl::memory_scope::device,
                                 sycl::access::address_space::global_space>
                    a(cnt[g - 1]);
                sycl::atomic_ref<unsigned, sycl::memory_order::relaxed, sycl::memory_scope::device,
                                 sycl::access::address_space::global_space>
                    ea(err[0]);
                unsigned n = 0;
                while (a.load(sycl::memory_order::acquire) < prev) {
                    if ((++n & 1023u) == 0 && ea.load() != 0) break;
                    if (n > (1u << 20)) {
                        ea.store(1u);
                        break;
                    }
                }
            }
            sycl::group_barrier(sg);
        }
        if (r < R) pre.dot(sg, lane, r, x, y);
        sycl::group_barrier(sg);
        if (lane == 0) {
            sycl::atomic_ref<unsigned, sycl::memory_order::acq_rel, sycl::memory_scope::device,
                             sycl::access::address_space::global_space>
                a(cnt[g]);
            a.fetch_add(1u, sycl::memory_order::release);
        }
    }
};

template <int MODE> struct Persist {
    Chain ch;
    unsigned G;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const unsigned nsgw = it.get_local_range(0) / 32;
        const unsigned gsg = it.get_group_linear_id() * nsgw + sg.get_group_linear_id(), nsg = G * nsgw;
        const bool lead = it.get_local_linear_id() == 0;
        uint32_t dummy = 0;
        for (int l = 0; l < L; ++l)
            for (int k = 0; k < NST; ++k) {
                const int g = l * NST + k;
                const float *x = (g & 1) ? ch.buf1 : ch.buf0;
                float *y = (g & 1) ? ch.buf0 : ch.buf1;
                if (g > 0) { // wait for stage g - 1 (all work-groups)
                    if (MODE > 0) dummy += touch(sg, gsg, nsg, SR[k], rbytes(SC[k]), ch.w[l][k], MODE == 2);
                    if (lead) {
                        sycl::atomic_ref<unsigned, sycl::memory_order::acq_rel, sycl::memory_scope::device,
                                         sycl::access::address_space::global_space>
                            a(ch.cnt[g - 1]);
                        sycl::atomic_ref<unsigned, sycl::memory_order::relaxed, sycl::memory_scope::device,
                                         sycl::access::address_space::global_space>
                            ea(ch.err[0]);
                        unsigned n = 0;
                        while (a.load(sycl::memory_order::acquire) < G) {
                            if ((++n & 1023u) == 0 && ea.load() != 0) break; // an earlier wait gave up: no more waiting
                            if (n > (1u << 20)) {
                                ea.store(1u);
                                break;
                            }
                        }
                    }
                    sycl::group_barrier(it.get_group());
                }
                switch (k) {
                case 0: rows_of<SC[0]>(sg, lane, gsg, nsg, SR[0], ch.w[l][0], x, y); break;
                case 1: rows_of<SC[1]>(sg, lane, gsg, nsg, SR[1], ch.w[l][1], x, y); break;
                case 2: rows_of<SC[2]>(sg, lane, gsg, nsg, SR[2], ch.w[l][2], x, y); break;
                case 3: rows_of<SC[3]>(sg, lane, gsg, nsg, SR[3], ch.w[l][3], x, y); break;
                case 4: rows_of<SC[4]>(sg, lane, gsg, nsg, SR[4], ch.w[l][4], x, y); break;
                default: rows_of<SC[5]>(sg, lane, gsg, nsg, SR[5], ch.w[l][5], x, y); break;
                }
                sycl::group_barrier(it.get_group());
                if (lead) {
                    sycl::atomic_ref<unsigned, sycl::memory_order::acq_rel, sycl::memory_scope::device,
                                     sycl::access::address_space::global_space>
                        a(ch.cnt[g]);
                    a.fetch_add(1u, sycl::memory_order::release);
                }
            }
        if (dummy == 0x9E3779B9u && gsg == 0 && lane == 0) ch.err[1] = dummy; // keeps the touches
    }
};

struct Floor {
    const uint32_t *p;
    size_t words; // multiple of 32 * 8
    uint32_t *out;
    void operator()(sycl::nd_item<1> it) const {
        sycl::sub_group sg = it.get_sub_group();
        const size_t nsg = it.get_global_range(0) / 32;
        size_t s = it.get_group_linear_id() * (it.get_local_range(0) / 32) + sg.get_group_linear_id();
        uint32_t acc = 0;
        for (size_t o = s * 256; o < words; o += nsg * 256) {
            const auto v = sg_bloadN<8>(sg, p + o);
            acc += v[0] ^ v[1] ^ v[2] ^ v[3] ^ v[4] ^ v[5] ^ v[6] ^ v[7];
        }
        if (acc == 0x9E3779B9u) out[0] = acc;
    }
};

int main(int argc, char **argv) {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const auto dev = q.get_device();
    const unsigned G = argc > 1 ? (unsigned)atoi(argv[1]) : 32;
    std::printf("%s, compute units %u, G = %u work-groups of 512\n", dev.get_info<sycl::info::device::name>().c_str(),
                dev.get_info<sycl::info::device::max_compute_units>(), G);
    std::mt19937 rng(23);
    std::uniform_int_distribution<int> ub(0, 255);
    std::normal_distribution<float> nd(0.f, 1.f);
    size_t layer_bytes = 0;
    for (int k = 0; k < NST; ++k) layer_bytes += (size_t)SR[k] * rbytes(SC[k]);
    const size_t total = layer_bytes * L;
    std::printf("weights %.1f MB per layer, %.1f MB per chain of %d layers\n", layer_bytes / 1e6, total / 1e6, L);
    std::vector<uint8_t> hw(total);
    {
        size_t off = 0;
        for (int l = 0; l < L; ++l)
            for (int k = 0; k < NST; ++k) {
                const size_t rb = rbytes(SC[k]);
                for (unsigned r = 0; r < SR[k]; ++r) {
                    uint8_t *row = &hw[off + (size_t)r * rb];
                    for (unsigned i = 0; i < SC[k] * 32; ++i) row[i] = (uint8_t)ub(rng);
                    uint16_t *dp = reinterpret_cast<uint16_t *>(row + SC[k] * 32);
                    for (unsigned i = 0; i < SC[k]; ++i) dp[i] = (uint16_t)(0x1000 + (ub(rng) & 0x3ff)); // ~1.2e-4
                    for (size_t i = SC[k] * 34; i < rb; ++i) row[i] = 0;
                }
                off += (size_t)SR[k] * rb;
            }
    }
    uint8_t *w = sycl::malloc_device<uint8_t>(total, q);
    q.memcpy(w, hw.data(), total).wait();
    std::vector<float> hx(BUF);
    for (auto &v : hx) v = nd(rng);
    constexpr int NF = 8; // A, P0, P1, P2, P3, P4, Q, Qi
    Chain ch[NF];
    for (int f = 0; f < NF; ++f) {
        size_t off = 0;
        for (int l = 0; l < L; ++l)
            for (int k = 0; k < NST; ++k) {
                ch[f].w[l][k] = w + off;
                off += (size_t)SR[k] * rbytes(SC[k]);
            }
        ch[f].buf0 = sycl::malloc_device<float>(BUF, q);
        ch[f].buf1 = sycl::malloc_device<float>(BUF, q);
        ch[f].cnt = sycl::malloc_device<unsigned>(L * NST, q);
        ch[f].err = sycl::malloc_device<unsigned>(2, q);
        q.fill(ch[f].err, 0u, 2);
    }
    uint32_t *fout = sycl::malloc_device<uint32_t>(1, q);
    q.wait();
    auto reset = [&](int f) {
        q.memcpy(ch[f].buf0, hx.data(), BUF * 4);
        q.memcpy(ch[f].buf1, hx.data(), BUF * 4);
        q.fill(ch[f].cnt, 0u, L * NST);
    };
    // A: one launch per stage
    auto run_a = [&](const Chain &c) {
        sycl::event first, last;
        for (int l = 0; l < L; ++l)
            for (int k = 0; k < NST; ++k) {
                const int g = l * NST + k;
                const float *x = (g & 1) ? c.buf1 : c.buf0;
                float *y = (g & 1) ? c.buf0 : c.buf1;
                const size_t nwg = (SR[k] + 15) / 16;
                const uint8_t *wk = c.w[l][k];
                sycl::event e;
                auto go = [&](auto kk) {
                    e = q.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                        kk(it, wk, x, y);
                    });
                };
                switch (k) {
                case 0: go(GemvQ8P<SC[0], ActF32>{SR[0], 0}); break;
                case 1: go(GemvQ8P<SC[1], ActF32>{SR[1], 0}); break;
                case 2: go(GemvQ8P<SC[2], ActF32>{SR[2], 0}); break;
                case 3: go(GemvQ8P<SC[3], ActF32>{SR[3], 0}); break;
                case 4: go(GemvQ8P<SC[4], ActF32>{SR[4], 0}); break;
                default: go(GemvQ8P<SC[5], ActF32>{SR[5], 0}); break;
                }
                if (g == 0) first = e;
                last = e;
            }
        return std::make_pair(first, last);
    };
    auto run_p = [&](int mode, const Chain &c) {
        sycl::event e;
        auto go = [&](auto kk) {
            e = q.parallel_for(sycl::nd_range<1>((size_t)G * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it); });
        };
        if (mode == 0) go(Persist<0>{c, G});
        else if (mode == 1) go(Persist<1>{c, G});
        else if (mode == 2) go(Persist<2>{c, G});
        else if (mode == 3) go(PersistS<3>{c, G});
        else go(PersistS<4>{c, G});
        return std::make_pair(e, e);
    };
    sycl::queue qo{q.get_context(), q.get_device(), {sycl::property::queue::enable_profiling{}}}; // out of order
    auto run_q = [&](const Chain &c, bool ooo) {
        sycl::queue &qq = ooo ? qo : q;
        sycl::event first, last;
        for (int l = 0; l < L; ++l)
            for (int k = 0; k < NST; ++k) {
                const int g = l * NST + k;
                const float *x = (g & 1) ? c.buf1 : c.buf0;
                float *y = (g & 1) ? c.buf0 : c.buf1;
                const size_t nwg = (SR[k] + 15) / 16;
                const unsigned prev = g > 0 ? (SR[(k + NST - 1) % NST] + 15) / 16 * 16 : 0;
                sycl::event e;
                auto go = [&](auto kk) {
                    e = qq.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it); });
                };
                switch (k) {
                case 0: go(QStage<SC[0]>{c.w[l][0], x, y, SR[0], prev, g, c.cnt, c.err}); break;
                case 1: go(QStage<SC[1]>{c.w[l][1], x, y, SR[1], prev, g, c.cnt, c.err}); break;
                case 2: go(QStage<SC[2]>{c.w[l][2], x, y, SR[2], prev, g, c.cnt, c.err}); break;
                case 3: go(QStage<SC[3]>{c.w[l][3], x, y, SR[3], prev, g, c.cnt, c.err}); break;
                case 4: go(QStage<SC[4]>{c.w[l][4], x, y, SR[4], prev, g, c.cnt, c.err}); break;
                default: go(QStage<SC[5]>{c.w[l][5], x, y, SR[5], prev, g, c.cnt, c.err}); break;
                }
                if (g == 0) first = e;
                last = e;
            }
        if (ooo) qo.wait();
        return std::make_pair(first, last);
    };
    auto run_f = [&]() {
        const size_t words = total / 4 / 256 * 256;
        const Floor fk{reinterpret_cast<const uint32_t *>(w), words, fout};
        sycl::event e = q.parallel_for(sycl::nd_range<1>((size_t)1024 * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { fk(it); });
        return std::make_pair(e, e);
    };
    // correctness: one chain per form from the same inputs; final buffers bitwise against A
    for (int f = 0; f < NF; ++f) reset(f);
    q.wait();
    run_a(ch[0]);
    for (int f = 1; f < NF; ++f) {
        if (f <= 5) run_p(f - 1, ch[f]);
        else run_q(ch[f], f == 6);
    }
    q.wait();
    long bad = 0;
    std::vector<float> r0(BUF), r1(BUF);
    std::vector<unsigned> herr(2);
    const char *names[NF + 1] = {"A one launch per stage", "P0 persistent", "P1 persistent + next rows read early",
                                 "P2 persistent + first next row early", "P3 per-sub-group sync + row in registers",
                                 "P4 per-sub-group sync only", "Q launches, no barriers, weights first",
                                 "Qi Q's kernels in order", "F floor: read the bytes"};
    for (int f = 1; f < NF; ++f) {
        for (int b = 0; b < 2; ++b) {
            q.memcpy(r0.data(), b ? ch[0].buf1 : ch[0].buf0, BUF * 4);
            q.memcpy(r1.data(), b ? ch[f].buf1 : ch[f].buf0, BUF * 4).wait();
            if (std::memcmp(r0.data(), r1.data(), BUF * 4)) { ++bad; std::printf("%s: buffer %d DIFFERS\n", names[f], b); }
        }
        q.memcpy(herr.data(), ch[f].err, 8).wait();
        if (herr[0]) { ++bad; std::printf("%s: a wait gave up\n", names[f]); }
    }
    // timing
    std::vector<double> tm[NF + 1];
    for (int rep = 0; rep < 12; ++rep) {
        std::vector<std::pair<int, std::pair<sycl::event, sycl::event>>> evs;
        for (int f = 0; f <= NF; ++f) {
            if (f < NF) reset(f);
            q.wait(); // the out-of-order form must not overlap the others
            auto ee = f == 0 ? run_a(ch[0]) : f <= 5 ? run_p(f - 1, ch[f]) : f < NF ? run_q(ch[f], f == 6) : run_f();
            evs.push_back({f, ee});
        }
        q.wait();
        if (rep < 2) continue; // warm-up
        for (auto &[f, ee] : evs) tm[f].push_back(ev_us(ee.first, ee.second));
    }
    for (int f = 1; f < NF; ++f) {
        q.memcpy(herr.data(), ch[f].err, 8).wait();
        if (herr[0]) { ++bad; std::printf("%s: a wait gave up (timing runs)\n", names[f]); }
    }
    std::printf("%-40s %10s %10s %12s %10s\n", "form", "median us", "min us", "us per layer", "GB/s");
    for (int f = 0; f <= NF; ++f) {
        auto t = tm[f];
        std::sort(t.begin(), t.end());
        const double med = t[t.size() / 2];
        std::printf("%-40s %10.1f %10.1f %12.2f %10.1f\n", names[f], med, t[0], med / L, total / med * 1e-3);
    }
    std::printf(bad ? "FAIL (%ld)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
