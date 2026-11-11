// The sparse attention's output step (SparseOutJB<512, 1, 16>: out[h][j] = sum over the list's slots i, in slot
// order, of w[h][i] * row(slot i)[j], slots < 0 skipped; ry = out with the last 64 dims rotated back) took
// ~22 us per layer in the engine once the list is 640 slots long (any context past ~640 tokens), 7.6 us at 160.
// One sub-group per (head, 64 columns): 128 sub-groups for 16 heads, each walking all 640 slots with its own
// loads. Forms here, outputs compared BITWISE with SparseOutJB<512, 1, 16> (out and ry), GPU time each:
//   A   SparseOutJB<512, 1, 16>            (the engine)
//   B   SparseOutJB<512, 1, 32>            (32 loads in flight)
//   F   SparseOutJBF<512, U>               (A with the skip of a slot < 0 written as an added -0.0f: no branch per
//       slot. x + -0 == x for every float, +0 and -0 included, so each output is the same)
//   S   SparseOutJS<HG, CH, F32, BF>       (the rows staged in local memory: a work-group of HG sub-groups =
//       HG heads of one 64-column span; chunk by chunk (CH slots) its sub-groups load the row pieces into local
//       memory, the next chunk's loads issued before this one is summed; each head's sums from local memory in
//       the same order with the same operations. F32: the pieces stored as f32 (the bf16 shift once per piece);
//       BF: the skip as an added -0.0f, as F)
// (Round 18 s1 also timed SparseOutJB<512, 1, 16, true> (pipelined loads, 10-15 % slower) and SparseOutJS with
// 4 or 8 heads per work-group (slower: each sub-group then also loads more pieces); all bitwise = A.)
// Lists: window slots 0..127 then compressed slots 128 + row (rows ascending, as the selects give them);
// weights softmax-like (positive) or signed normals with zeros of both signs; some lists with -1 slots (some of
// them with NaN weights: the softmax leaves a skipped slot's raw score).
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_sparse_out.cpp -o bench_sparse_out
//   ONEAPI_DEVICE_SELECTOR=level_zero:1 ./bench_sparse_out
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

template <unsigned HD, unsigned HG_, unsigned CH, bool F32 = false, bool BF = false, unsigned U = 16> struct SparseOutJS {
    static constexpr unsigned HG = HG_, PER_HEAD = HD / 64, LP = CH / HG, NK = CH / 32, WPS = F32 ? 64 : 32;
    static constexpr size_t SLM = 2 * (size_t)CH * WPS; // 32-bit words: two chunk buffers
    static_assert(CH % 32 == 0 && CH % HG == 0 && LP >= 1 && LP <= 32 && 32 % U == 0);
    int n_idx, heads, win_rows; // n_idx % 32 == 0
    float *ry = nullptr;
    const float *cosb = nullptr, *sinb = nullptr;
    static size_t groups(int heads) { return (size_t)PER_HEAD * ((heads + HG - 1) / HG); }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out, uint32_t *lm) const {
        run(it, (unsigned)it.get_group_linear_id(), kvw, kvc, idxs, w, out, lm);
    }
    [[gnu::always_inline]] inline void run(sycl::nd_item<1> it, unsigned grp, const uint16_t *kvw, const uint16_t *kvc,
                                           const int32_t *idxs, const float *w, float *out, uint32_t *lm) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), g = sg.get_group_linear_id();
        const unsigned base = (grp % PER_HEAD) * 64;
        const int h = (int)((grp / PER_HEAD) * HG + g);
        const bool act = h < heads;
        const int n = n_idx, wr = win_rows, nch = (n + (int)CH - 1) / (int)CH;
        const float *wh = w + (size_t)(act ? h : 0) * n;
        auto row_addr = [&](int slot) {
            const int s0 = slot < 0 ? 0 : slot;
            const uint16_t *k = s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD;
            return reinterpret_cast<const uint32_t *>(k + base);
        };
        // loader slots of chunk c: lane u < LP holds slot c * CH + g * LP + u
        auto lslots = [&](int c) {
            const int i = c * (int)CH + (int)(g * LP + lane);
            return lane < LP && i < n ? idxs[i] : -1;
        };
        uint32_t pc[LP];
        auto issue = [&](int c, int ls) {
#pragma unroll
            for (unsigned u = 0; u < LP; ++u)
                if (c * (int)CH + (int)(g * LP + u) < n) pc[u] = sg_bloadN<1>(sg, row_addr(sycl::select_from_group(sg, ls, u)))[0];
        };
        auto put = [&](int c) {
            uint32_t *b = lm + (size_t)(c & 1) * CH * WPS;
#pragma unroll
            for (unsigned u = 0; u < LP; ++u) {
                if (c * (int)CH + (int)(g * LP + u) >= n) continue;
                const unsigned p = g * LP + u;
                if constexpr (F32) {
                    b[p * 64 + 2 * lane] = pc[u] << 16;
                    b[p * 64 + 2 * lane + 1] = pc[u] & 0xFFFF0000u;
                } else
                    b[p * 32 + lane] = pc[u];
            }
        };
        // this head's slots and weights of chunk c (lane l of k: slot c * CH + 32 k + l)
        int csl[NK], nsl[NK];
        float cwl[NK], nwl[NK];
        auto lw = [&](int c, int (&s)[NK], float (&x)[NK]) {
#pragma unroll
            for (unsigned k = 0; k < NK; ++k) {
                const int i = c * (int)CH + (int)(32 * k + lane);
                const bool in = c * (int)CH + (int)(32 * k) < n;
                s[k] = in ? idxs[i] : -1;
                x[k] = in ? wh[i] : 0.0f;
            }
        };
        float o0 = 0, o1 = 0;
        int ls = lslots(0);
        issue(0, ls);
        lw(0, csl, cwl);
        if (nch > 1) ls = lslots(1);
        put(0);
        sycl::group_barrier(it.get_group());
        for (int c = 0; c < nch; ++c) {
            const bool more = c + 1 < nch;
            if (more) {
                issue(c + 1, ls);
                lw(c + 1, nsl, nwl);
                if (c + 2 < nch) ls = lslots(c + 2);
            }
            if (act) {
                const uint32_t *b = lm + (size_t)(c & 1) * CH * WPS;
#pragma unroll
                for (unsigned k = 0; k < NK; ++k) {
                    if (c * (int)CH + (int)(32 * k) >= n) break;
#pragma unroll
                    for (unsigned u0 = 0; u0 < 32; u0 += U) {
                        uint32_t x0[U], x1[U];
#pragma unroll
                        for (unsigned u = 0; u < U; ++u) {
                            const unsigned p = 32 * k + u0 + u;
                            if constexpr (F32) {
                                x0[u] = b[p * 64 + 2 * lane];
                                x1[u] = b[p * 64 + 2 * lane + 1];
                            } else {
                                const uint32_t v = b[p * 32 + lane];
                                x0[u] = v << 16;
                                x1[u] = v & 0xFFFF0000u;
                            }
                        }
#pragma unroll
                        for (unsigned u = 0; u < U; ++u) {
                            const int slot = sycl::select_from_group(sg, csl[k], u0 + u);
                            const float wu = sycl::select_from_group(sg, cwl[k], u0 + u);
                            if constexpr (BF) {
                                const float p0 = wu * sycl::bit_cast<float>(x0[u]), p1 = wu * sycl::bit_cast<float>(x1[u]);
                                o0 += slot >= 0 ? p0 : -0.0f;
                                o1 += slot >= 0 ? p1 : -0.0f;
                            } else if (slot >= 0) {
                                o0 += wu * sycl::bit_cast<float>(x0[u]);
                                o1 += wu * sycl::bit_cast<float>(x1[u]);
                            }
                        }
                    }
                }
            }
            if (more) {
                put(c + 1);
#pragma unroll
                for (unsigned k = 0; k < NK; ++k) {
                    csl[k] = nsl[k];
                    cwl[k] = nwl[k];
                }
            }
            sycl::group_barrier(it.get_group());
        }
        if (!act) return;
        float *oh = out + (size_t)h * HD + base;
        oh[2 * lane] = o0;
        oh[2 * lane + 1] = o1;
        if (ry) {
            float a0 = o0, a1 = o1;
            if (base == HD - 64) {
                const float re = a0, im = a1, cs = cosb[lane], sn = -sinb[lane];
                a0 = re * cs - im * sn;
                a1 = re * sn + im * cs;
            }
            float *yh = ry + (size_t)h * HD + base;
            yh[2 * lane] = a0;
            yh[2 * lane + 1] = a1;
        }
    }
};

// SparseOutJB<HD, 1, U> (no pipe) with the skip written without a branch: a skipped slot adds -0.0f, which leaves
// every float as it is (x + -0 == x, also for x = +0 and -0), so each output is the same as when the add is skipped;
// the products of skipped slots (any weight, row 0's values) are formed and dropped.
template <unsigned HD, unsigned U = 16> struct SparseOutJBF {
    static constexpr unsigned PER_HEAD = HD / 64;
    int n_idx, heads, win_rows;
    float *ry = nullptr;
    const float *cosb = nullptr, *sinb = nullptr;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned grp = (unsigned)it.get_group_linear_id(), lane = sg.get_local_linear_id();
        const int h = (int)(grp / PER_HEAD);
        const unsigned base = (grp % PER_HEAD) * 64;
        if (h >= heads) return;
        const float *wh = w + (size_t)h * n_idx;
        float o0 = 0, o1 = 0;
        const int wr = win_rows;
        auto row_addr = [&](int slot) {
            const int s0 = slot < 0 ? 0 : slot;
            const uint16_t *k = s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD;
            return reinterpret_cast<uintptr_t>(k + base);
        };
        for (int i0 = 0; i0 < n_idx; i0 += 32) {
            const int sl = idxs[i0 + lane];
            const float wl = wh[i0 + lane];
            const uintptr_t ra = row_addr(sl);
#pragma unroll
            for (unsigned u0 = 0; u0 < 32; u0 += U) {
                uint32_t kv[U];
#pragma unroll
                for (unsigned u = 0; u < U; ++u)
                    kv[u] = sg_bloadN<1>(sg, reinterpret_cast<const uint32_t *>(sycl::select_from_group(sg, ra, u0 + u)))[0];
#pragma unroll
                for (unsigned u = 0; u < U; ++u) {
                    const bool ok = sycl::select_from_group(sg, sl, u0 + u) >= 0;
                    const float wu = sycl::select_from_group(sg, wl, u0 + u);
                    const float p0 = wu * sycl::bit_cast<float>(kv[u] << 16), p1 = wu * sycl::bit_cast<float>(kv[u] & 0xFFFF0000u);
                    o0 += ok ? p0 : -0.0f;
                    o1 += ok ? p1 : -0.0f;
                }
            }
        }
        float *oh = out + (size_t)h * HD + base;
        oh[2 * lane] = o0;
        oh[2 * lane + 1] = o1;
        if (ry) {
            float a0 = o0, a1 = o1;
            if (base == HD - 64) {
                const float re = a0, im = a1, cs = cosb[lane], sn = -sinb[lane];
                a0 = re * cs - im * sn;
                a1 = re * sn + im * cs;
            }
            float *yh = ry + (size_t)h * HD + base;
            yh[2 * lane] = a0;
            yh[2 * lane + 1] = a1;
        }
    }
};

// SparseOutJS<.., F32, BF> with one column per lane (twice the work-groups): work-group = HG sub-groups = HG heads of
// one 32-column span (HD / 32 spans); 64-byte row pieces (32 bf16) per slot, stored in local memory as f32; the
// skip as an added -0.0f. Lane l keeps column base + l; the epilogue's pairs (2i, 2i + 1) are lanes (2m, 2m + 1),
// the partner's value by a shuffle, the same expressions.
template <unsigned HD, unsigned HG_, unsigned CH, unsigned U = 16> struct SparseOutJC {
    static constexpr unsigned HG = HG_, PER_HEAD = HD / 32, LP = CH / HG, NK = CH / 32;
    static constexpr size_t SLM = 2 * (size_t)CH * 32;
    static_assert(CH % 32 == 0 && CH % HG == 0 && LP >= 1 && LP <= 32 && 32 % U == 0);
    int n_idx, heads, win_rows;
    float *ry = nullptr;
    const float *cosb = nullptr, *sinb = nullptr;
    static size_t groups(int heads) { return (size_t)PER_HEAD * ((heads + HG - 1) / HG); }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out, uint32_t *lm) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned grp = (unsigned)it.get_group_linear_id(), lane = sg.get_local_linear_id(), g = sg.get_group_linear_id();
        const unsigned base = (grp % PER_HEAD) * 32;
        const int h = (int)((grp / PER_HEAD) * HG + g);
        const bool act = h < heads;
        const int n = n_idx, wr = win_rows, nch = (n + (int)CH - 1) / (int)CH;
        const float *wh = w + (size_t)(act ? h : 0) * n;
        auto row_addr = [&](int slot) {
            const int s0 = slot < 0 ? 0 : slot;
            return (s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD) + base;
        };
        auto lslots = [&](int c) {
            const int i = c * (int)CH + (int)(g * LP + lane);
            return lane < LP && i < n ? idxs[i] : -1;
        };
        uint16_t pc[LP];
        auto issue = [&](int c, int ls) {
#pragma unroll
            for (unsigned u = 0; u < LP; ++u)
                if (c * (int)CH + (int)(g * LP + u) < n) pc[u] = sg_bloadN<1>(sg, row_addr(sycl::select_from_group(sg, ls, u)))[0];
        };
        auto put = [&](int c) {
            uint32_t *b = lm + (size_t)(c & 1) * CH * 32;
#pragma unroll
            for (unsigned u = 0; u < LP; ++u)
                if (c * (int)CH + (int)(g * LP + u) < n) b[(g * LP + u) * 32 + lane] = (uint32_t)pc[u] << 16;
        };
        int csl[NK], nsl[NK];
        float cwl[NK], nwl[NK];
        auto lw = [&](int c, int (&s)[NK], float (&x)[NK]) {
#pragma unroll
            for (unsigned k = 0; k < NK; ++k) {
                const int i = c * (int)CH + (int)(32 * k + lane);
                const bool in = c * (int)CH + (int)(32 * k) < n;
                s[k] = in ? idxs[i] : -1;
                x[k] = in ? wh[i] : 0.0f;
            }
        };
        float o = 0;
        int ls = lslots(0);
        issue(0, ls);
        lw(0, csl, cwl);
        if (nch > 1) ls = lslots(1);
        put(0);
        sycl::group_barrier(it.get_group());
        for (int c = 0; c < nch; ++c) {
            const bool more = c + 1 < nch;
            if (more) {
                issue(c + 1, ls);
                lw(c + 1, nsl, nwl);
                if (c + 2 < nch) ls = lslots(c + 2);
            }
            if (act) {
                const uint32_t *b = lm + (size_t)(c & 1) * CH * 32;
#pragma unroll
                for (unsigned k = 0; k < NK; ++k) {
                    if (c * (int)CH + (int)(32 * k) >= n) break;
#pragma unroll
                    for (unsigned u0 = 0; u0 < 32; u0 += U) {
                        uint32_t x[U];
#pragma unroll
                        for (unsigned u = 0; u < U; ++u) x[u] = b[(32 * k + u0 + u) * 32 + lane];
#pragma unroll
                        for (unsigned u = 0; u < U; ++u) {
                            const bool ok = sycl::select_from_group(sg, csl[k], u0 + u) >= 0;
                            const float p0 = sycl::select_from_group(sg, cwl[k], u0 + u) * sycl::bit_cast<float>(x[u]);
                            o += ok ? p0 : -0.0f;
                        }
                    }
                }
            }
            if (more) {
                put(c + 1);
#pragma unroll
                for (unsigned k = 0; k < NK; ++k) {
                    csl[k] = nsl[k];
                    cwl[k] = nwl[k];
                }
            }
            sycl::group_barrier(it.get_group());
        }
        const float pr = sycl::select_from_group(sg, o, lane ^ 1u);
        if (!act) return;
        out[(size_t)h * HD + base + lane] = o;
        if (ry) {
            float a = o;
            if (base >= HD - 64) {
                const unsigned i = (base - (HD - 64) + lane) / 2;
                const float cs = cosb[i], sn = -sinb[i];
                if (lane & 1) {
                    const float re = pr, im = o;
                    a = re * sn + im * cs;
                } else {
                    const float re = o, im = pr;
                    a = re * cs - im * sn;
                }
            }
            ry[(size_t)h * HD + base + lane] = a;
        }
    }
};

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const auto dev = q.get_device();
    std::printf("%s: %u compute units, local memory %zu KiB, max work-group %zu\n", dev.get_info<sycl::info::device::name>().c_str(),
                dev.get_info<sycl::info::device::max_compute_units>(), (size_t)dev.get_info<sycl::info::device::local_mem_size>() / 1024,
                dev.get_info<sycl::info::device::max_work_group_size>());
    constexpr unsigned HD = 512, W = 128, CROWS = 24000, MAXH = 16, MAXI = 640;
    uint16_t *kvw = sycl::malloc_device<uint16_t>((size_t)W * HD, q), *kvc = sycl::malloc_device<uint16_t>((size_t)CROWS * HD, q);
    int32_t *ix = sycl::malloc_device<int32_t>(MAXI, q);
    float *wt = sycl::malloc_device<float>((size_t)MAXH * MAXI, q), *cs = sycl::malloc_device<float>(64, q);
    constexpr int NF = 9;
    float *ob[NF], *yb[NF];
    for (int f = 0; f < NF; ++f) {
        ob[f] = sycl::malloc_device<float>((size_t)MAXH * HD, q);
        yb[f] = sycl::malloc_device<float>((size_t)MAXH * HD, q);
    }
    const char *names[NF] = {"A SparseOutJB<512,1,16> (engine)", "F SparseOutJBF<512,32> (no branch)",
                             "S SparseOutJS<16,128,f32> no branch", "S SparseOutJS<16,64,f32> no branch",
                             "C SparseOutJC<16,128> (column per lane)", "C SparseOutJC<8,128>", "C SparseOutJC<16,64>",
                             "C SparseOutJC<16,256>", "C SparseOutJC<16,128,8>"};
    std::mt19937 rng(11);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::uniform_int_distribution<int> ue(-12, 8);
    auto bf = [](float f) { uint32_t u; std::memcpy(&u, &f, 4); return (uint16_t)(u >> 16); };
    {
        std::vector<uint16_t> hw((size_t)W * HD), hc((size_t)CROWS * HD);
        for (auto &v : hw) v = bf(nd(rng) * std::ldexp(1.0f, ue(rng)));
        for (auto &v : hc) v = bf(nd(rng) * std::ldexp(1.0f, ue(rng)));
        for (int i = 0; i < 200; ++i) hc[(size_t)(rng() % hc.size())] = (i & 1) ? 0x8000 : 0; // zeros of both signs
        q.memcpy(kvw, hw.data(), hw.size() * 2);
        q.memcpy(kvc, hc.data(), hc.size() * 2).wait();
        std::vector<float> hcs(64);
        for (auto &v : hcs) v = nd(rng);
        q.memcpy(cs, hcs.data(), 64 * 4).wait();
    }
    // the forms; each returns its launch's event
    auto sg_launch = [&](auto k, size_t groups, auto... a) {
        return q.parallel_for(sycl::nd_range<1>(groups * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, a...); });
    };
    auto js = [&](auto k, int heads, float *o, float *y) {
        using K = decltype(k);
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<uint32_t, 1> lt(K::SLM, h);
            h.parallel_for(sycl::nd_range<1>(K::groups(heads) * 32 * K::HG, 32 * K::HG),
                           [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                               k(it, (const uint16_t *)kvw, (const uint16_t *)kvc, (const int32_t *)ix, (const float *)wt, o,
                                 &lt[0]);
                           });
        });
    };
    auto run = [&](int f, int n, int heads) -> sycl::event {
        float *o = ob[f], *y = yb[f];
        auto set = [&](auto k) {
            k.ry = y;
            k.cosb = cs;
            k.sinb = cs + 32;
            return k;
        };
        const size_t gs = (size_t)heads * HD / 64;
        switch (f) {
        case 0: return sg_launch(set(SparseOutJB<HD, 1, 16>{n, heads, (int)W}), gs, (const uint16_t *)kvw, (const uint16_t *)kvc, (const int32_t *)ix, (const float *)wt, o);
        case 1: return sg_launch(set(SparseOutJBF<HD, 32>{n, heads, (int)W}), gs, (const uint16_t *)kvw, (const uint16_t *)kvc, (const int32_t *)ix, (const float *)wt, o);
        case 2: return js(set(SparseOutJS<HD, 16, 128, true, true>{n, heads, (int)W}), heads, o, y);
        case 3: return js(set(SparseOutJS<HD, 16, 64, true, true>{n, heads, (int)W}), heads, o, y);
        case 4: return js(set(SparseOutJC<HD, 16, 128>{n, heads, (int)W}), heads, o, y);
        case 5: return js(set(SparseOutJC<HD, 8, 128>{n, heads, (int)W}), heads, o, y);
        case 6: return js(set(SparseOutJC<HD, 16, 64>{n, heads, (int)W}), heads, o, y);
        case 7: return js(set(SparseOutJC<HD, 16, 256>{n, heads, (int)W}), heads, o, y);
        default: return js(set(SparseOutJC<HD, 16, 128, 8>{n, heads, (int)W}), heads, o, y);
        }
    };
    q.fill(ix, 5, MAXI);
    q.fill(wt, 0.001f, (size_t)MAXH * MAXI).wait();
    for (int r = 0; r < 400; ++r) run(0, 640, 16); // warm-up (valid slots)
    q.wait();
    const char *kinds[3] = {"softmax weights", "signed weights, -1 slots", "list tail -1"};
    long bad = 0;
    std::printf("%-26s %4s %5s", "list", "n", "heads");
    for (int f = 0; f < NF; ++f) std::printf(" | %c%d", names[f][0], f);
    std::printf("   (median us; y = out and ry bitwise = A)\n");
    std::vector<std::vector<double>> all(NF);
    for (int kind = 0; kind < 3; ++kind)
        for (int n : {640, 160, 128})
            for (int heads : {16, 8}) {
                std::vector<int32_t> hi(MAXI);
                for (int i = 0; i < 128; ++i) hi[i] = i;
                {
                    std::vector<int> rows(CROWS);
                    for (int r = 0; r < (int)CROWS; ++r) rows[r] = r;
                    std::shuffle(rows.begin(), rows.end(), rng);
                    std::sort(rows.begin(), rows.begin() + 512);
                    for (int i = 0; i < 512; ++i) hi[128 + i] = 128 + rows[i];
                }
                if (n == 160) for (int i = 128 + 25; i < 160; ++i) hi[i] = -1; // a trimmed list: 25 rows
                if (kind == 1) for (int i = 0; i < n; ++i) if (rng() % 5 == 0) hi[i] = -1;
                if (kind == 2 && n == 640) for (int i = 640 - 97; i < 640; ++i) hi[i] = -1;
                std::vector<float> hw((size_t)MAXH * MAXI);
                for (int h = 0; h < heads; ++h) {
                    double s = 0;
                    for (int i = 0; i < n; ++i) {
                        float v = kind == 1 ? nd(rng) : std::exp(2.0f * nd(rng));
                        if (kind == 1 && rng() % 7 == 0) v = (rng() & 1) ? 0.0f : -0.0f;
                        hw[(size_t)h * n + i] = v;
                        s += v;
                    }
                    if (kind != 1) for (int i = 0; i < n; ++i) hw[(size_t)h * n + i] = float(hw[(size_t)h * n + i] / s);
                    if (kind == 1) for (int i = 0; i < n; ++i) if (hi[i] < 0 && i % 3 == 0) hw[(size_t)h * n + i] = std::nanf("");
                }
                q.memcpy(ix, hi.data(), MAXI * 4);
                q.memcpy(wt, hw.data(), hw.size() * 4).wait();
                for (int f = 0; f < NF; ++f) {
                    q.fill(ob[f], -7.0f, (size_t)MAXH * HD);
                    q.fill(yb[f], -7.0f, (size_t)MAXH * HD);
                }
                q.wait();
                const int REP = kind == 0 ? 60 : 6;
                std::vector<std::vector<double>> t(NF);
                for (int r = 0; r <= REP; ++r)
                    for (int f = 0; f < NF; ++f) {
                        auto e = run(f, n, heads);
                        e.wait();
                        if (r) t[f].push_back(ev_us(e));
                    }
                std::vector<float> ro((size_t)heads * HD), ryr((size_t)heads * HD), x((size_t)heads * HD), yy((size_t)heads * HD);
                q.memcpy(ro.data(), ob[0], ro.size() * 4);
                q.memcpy(ryr.data(), yb[0], ryr.size() * 4).wait();
                std::printf("%-26s %4d %5d", kinds[kind], n, heads);
                for (int f = 0; f < NF; ++f) {
                    std::sort(t[f].begin(), t[f].end());
                    if (kind == 0) all[f].push_back(t[f][t[f].size() / 2]);
                    bool same = true;
                    if (f) {
                        q.memcpy(x.data(), ob[f], x.size() * 4);
                        q.memcpy(yy.data(), yb[f], yy.size() * 4).wait();
                        same = !std::memcmp(x.data(), ro.data(), x.size() * 4) && !std::memcmp(yy.data(), ryr.data(), yy.size() * 4);
                        bad += !same;
                    }
                    std::printf(" | %5.1f %s", t[f][t[f].size() / 2], same ? "y" : "NO");
                }
                std::printf("\n");
            }
    std::printf("forms:\n");
    for (int f = 0; f < NF; ++f) std::printf("  %c%d %s\n", names[f][0], f, names[f]);
    std::printf(bad ? "FAIL (%ld differ)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
