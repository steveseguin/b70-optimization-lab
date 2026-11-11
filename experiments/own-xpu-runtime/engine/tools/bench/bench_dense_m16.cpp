// Q8_0 packed dense rows for blocks of 16 tokens (prompt reading) at one 12-head card's shapes: query-b 6144 x 1280,
// query-a + kv 1792 x 5120, output-b 864 x 8192, shared-expert down 864 x 2304, output-a 768 x 4096. The engine's
// forms (DenseRowsG<GemvQ8P, 4>; DenseRowsGR<.., 4, 4> from 4,096 rows) against token groups of 8 / 16 and row
// blocks, all BITWISE against the one-token kernel per token. Cold timing (the matrix evicted by READING 256 MiB
// before every launch, as in the engine where a layer's rows are not in the cache), plus two diagnostics of the
// engine form that are NOT the engine's values: warm (no eviction) and "x shared" (every token reads token 0's
// activations: how much the 16 tokens' activation reads cost). Round18 e80/e82 profiles: per launch 96-112 us for
// query-b, 61 for output-b, 25 for the shared down at ~1.1-1.8 T weight-tokens/s.
//   PCS=1: instead of timing, EU stall sampling (tools/bench/pcs.hpp) of the engine forms, 300 evict + launch pairs
//   each (needs root: sudo -S env LD_LIBRARY_PATH=... ZE_AFFINITY_MASK=1 PCS=1 ./bench_dense_m16).
//
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH; P=/opt/intel/oneapi/pti/latest
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src -I $P/include tools/bench/bench_dense_m16.cpp -o $S/bench_dense_m16 \
//     -L $P/lib -lpti_view
//   LD_LIBRARY_PATH=$P/lib:/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib \
//     ONEAPI_DEVICE_SELECTOR=level_zero:1 $S/bench_dense_m16
// Exit status 1 on any mismatch.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
#include "pcs.hpp"
using namespace ops41sycl;

// GemvQ8P::rowgr with other instruction sequences for the same values (round18 d3). The engine's Q8_0 rows spend
// ~6 instructions per weight and row on the decode (machine code of DenseRowsGR<GemvQ8P<40>, 4, 4>: shr, three
// movs for byte -> word -> float, an indirect-register mov for the scale broadcast, the scale multiply), next to
// the 2 per weight and token (multiply, add). Every form here computes e = d * float(q) exactly as before (the
// product of a half and an int8 is exact in float) and the sums in the same order:
//   D (scale): 0 = per-lane load + select_from_group (engine); 1 = a uniform load per chunk; 2 = uniform loads
//              of 8 scales at a time
//   V (int8 -> float): 0 = float(int8_t(uint8_t(w >> 8k))) (engine); 1 = bit_cast to vec<int8_t, 4>, element k;
//              2 = the 2^23 trick: bits ((byte ^ 0x80) | 0x4b000000) - 8388736.0f (exact: 2^23 + s + 128 - 2^23 - 128);
//              3 = float(int32_t(w << (24 - 8k)) >> 24)
template <unsigned C, unsigned D, unsigned V> struct Q8V {
    unsigned rows, xn;
    static inline float qf(uint32_t w, unsigned k) {
        if constexpr (V == 0) return float(int8_t(uint8_t(w >> (8 * k))));
        else if constexpr (V == 1) return float(sycl::bit_cast<sycl::vec<int8_t, 4>>(w)[k]);
        else if constexpr (V == 2)
            return sycl::bit_cast<float>((((w >> (8 * k)) & 0xffu) ^ 0x80u) | 0x4b000000u) - 8388736.0f;
        else return float(int32_t(w << (24 - 8 * k)) >> 24);
    }
    template <unsigned NT, unsigned R>
    [[gnu::always_inline]] inline void rowgr(sycl::sub_group sg, unsigned lane, unsigned r0, const uint8_t *w,
                                             const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        constexpr unsigned NQ = C / 4, SEGQ = Q8Seg<C>::v, ND = (C + 31) / 32;
        static_assert(NQ % SEGQ == 0 && (D != 2 || (SEGQ % 2 == 0 && C % 8 == 0)));
        constexpr size_t RB = ((size_t)C * 34 + 15) & ~(size_t)15;
        const float *xr = xn ? x + (size_t)(r0 / xn) * C * 32 : x;
        const uint32_t *qw[R];
        const uint16_t *dp[R];
        float dv[R][D == 0 ? ND : 1];
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *row = w + (size_t)(r0 + j < rows ? r0 + j : r0) * RB;
            dp[j] = reinterpret_cast<const uint16_t *>(row + (size_t)C * 32);
            if constexpr (D == 0) {
#pragma unroll
                for (unsigned k = 0; k < ND; ++k) dv[j][k] = 32 * k + lane < C ? iq3::half(dp[j][32 * k + lane]) : 0.0f;
            }
            qw[j] = reinterpret_cast<const uint32_t *>(row);
        }
        float sum[R][NT];
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) sum[j][t] = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NQ; s0 += SEGQ) {
            uint32_t q[R][SEGQ];
#pragma unroll
            for (unsigned j = 0; j < R; ++j)
#pragma unroll
                for (unsigned m = 0; m < SEGQ; ++m) q[j][m] = sg_bload(sg, qw[j] + (size_t)(s0 + m) * 32);
            float ds[R][D == 0 ? 1 : 4 * SEGQ];
            if constexpr (D == 1) {
#pragma unroll
                for (unsigned j = 0; j < R; ++j)
#pragma unroll
                    for (unsigned i = 0; i < 4 * SEGQ; ++i) ds[j][i] = iq3::half(dp[j][4 * s0 + i]);
            } else if constexpr (D == 2) {
#pragma unroll
                for (unsigned j = 0; j < R; ++j)
#pragma unroll
                    for (unsigned i8 = 0; i8 < SEGQ / 2; ++i8) {
                        const sycl::vec<uint16_t, 8> v = reinterpret_cast<const sycl::vec<uint16_t, 8> *>(dp[j] + 4 * s0)[i8];
#pragma unroll
                        for (unsigned e = 0; e < 8; ++e) ds[j][8 * i8 + e] = iq3::half(v[e]);
                    }
            }
#pragma unroll
            for (unsigned m = 0; m < SEGQ; ++m) {
                sycl::vec<float, 4> xv[NT];
#pragma unroll
                for (unsigned t = 0; t < NT; ++t) xv[t] = sg_bloadN<4>(sg, xr + t * xs + (size_t)(s0 + m) * 128);
#pragma unroll
                for (unsigned k = 0; k < 4; ++k) {
                    const unsigned c = (s0 + m) * 4 + k;
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) {
                        float d;
                        if constexpr (D == 0) d = sycl::select_from_group(sg, dv[j][c / 32], c % 32);
                        else d = ds[j][4 * m + k];
                        const float e = d * qf(q[j][m], k);
#pragma unroll
                        for (unsigned t = 0; t < NT; ++t) sum[j][t] = sum[j][t] + e * xv[t][k];
                    }
                }
            }
        }
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) sum[j][t] = sg_tree32(sg, sum[j][t]);
        if (lane == 0) {
#pragma unroll
            for (unsigned j = 0; j < R; ++j)
                if (r0 + j < rows)
#pragma unroll
                    for (unsigned t = 0; t < NT; ++t)
                        if (t < mt) y[t * ys + r0 + j] = sum[j][t];
        }
    }
    template <unsigned NT>
    [[gnu::always_inline]] inline void rowg(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        rowgr<NT, 1>(sg, lane, r, w, x, xs, y, ys, mt);
    }
};

static constexpr unsigned MT = 16;
static constexpr size_t FLUSH_WORDS = (size_t)64 << 20; // 256 MiB
static uint32_t *g_flush = nullptr;
static int g_fail = 0;
static bool g_pcs = false;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
static void flush(sycl::queue &q, uint32_t v) {
    const uint32_t *p = g_flush;
    uint32_t *o = g_flush;
    q.parallel_for(sycl::range<1>(FLUSH_WORDS / 4), [=](sycl::id<1> i) {
        const size_t b = (size_t)i[0];
        const uint32_t s = p[b] ^ p[b + FLUSH_WORDS / 4] ^ p[b + FLUSH_WORDS / 2] ^ p[b + 3 * FLUSH_WORDS / 4];
        if (s == v + 0x80000000u) o[b] = 0;
    });
}
template <typename T> T *dev_copy(sycl::queue &q, const std::vector<T> &h) {
    T *d = sycl::malloc_device<T>(h.size(), q);
    q.memcpy(d, h.data(), h.size() * sizeof(T)).wait();
    return d;
}
static std::vector<float> rand_f(size_t n, unsigned seed, float lo, float hi) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<float> u(lo, hi);
    std::vector<float> v(n);
    for (auto &f : v) f = u(rng);
    return v;
}
static std::vector<uint8_t> packed_q8(unsigned cols, unsigned rows, unsigned seed) {
    constexpr auto L = iq3::layout(iq3::Type::Q8_0);
    const size_t rb = (size_t)cols / L.elements * L.bytes, prb = pk41::packed_row_bytes(iq3::Type::Q8_0, cols);
    std::mt19937 rng(seed);
    std::vector<uint8_t> hw((size_t)rows * rb);
    for (auto &b : hw) b = uint8_t(rng());
    for (size_t blk = 0; blk < hw.size() / L.bytes; ++blk) {
        uint8_t *bp = hw.data() + blk * L.bytes;
        const uint16_t h = 0x1400 + (rng() & 0x3ff);
        bp[0] = h & 255;
        bp[1] = h >> 8;
    }
    std::vector<uint8_t> hp((size_t)rows * prb);
    for (size_t r = 0; r < rows; ++r) pk41::pack_row(iq3::Type::Q8_0, hw.data() + r * rb, hp.data() + r * prb, cols);
    return hp;
}

static std::vector<uint8_t> packed_q6k(unsigned cols, unsigned rows, unsigned seed) {
    constexpr auto L = iq3::layout(iq3::Type::Q6_K);
    const size_t rb = (size_t)cols / L.elements * L.bytes, prb = pk41::packed_row_bytes(iq3::Type::Q6_K, cols);
    std::mt19937 rng(seed);
    std::vector<uint8_t> hw((size_t)rows * rb);
    for (auto &b : hw) b = uint8_t(rng());
    for (size_t blk = 0; blk < hw.size() / L.bytes; ++blk) {
        uint8_t *bp = hw.data() + blk * L.bytes;
        const uint16_t h = 0x1400 + (rng() & 0x3ff);
        bp[208] = h & 255;
        bp[209] = h >> 8;
    }
    std::vector<uint8_t> hp((size_t)rows * prb);
    for (size_t r = 0; r < rows; ++r) pk41::pack_row(iq3::Type::Q6_K, hw.data() + r * rb, hp.data() + r * prb, cols);
    return hp;
}
template <typename K> struct Shape {
    K k;
    const uint8_t *w;
    const float *x;
    size_t xs, ys;
    float *yr, *ym;
    std::vector<float> ref;
    char name[48];
};
template <typename RW> static sycl::event launch(sycl::queue &q, const RW &rw) {
    const RowsP<RW> kr{rw};
    const size_t wg = 512, per = wg / 32, nwg = ((size_t)rw.n() + per - 1) / per;
    return q.parallel_for(sycl::nd_range<1>(nwg * wg, wg),
                          [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kr(it); });
}
template <typename RW> static double med_us(sycl::queue &q, const RW &rw, bool cold) {
    for (int i = 0; i < 20; ++i) launch(q, rw);
    q.wait();
    std::vector<double> t;
    for (unsigned rep = 0; rep < 15; ++rep) {
        if (cold) flush(q, rep);
        sycl::event e = launch(q, rw);
        q.wait();
        t.push_back(ev_us(e));
    }
    std::sort(t.begin(), t.end());
    return t[t.size() / 2];
}
template <typename K, typename RW> static bool same(sycl::queue &q, Shape<K> &s, const RW &rw) {
    const size_t n = (size_t)MT * s.ys;
    q.memset(s.ym, 0xff, n * 4).wait();
    launch(q, rw).wait();
    std::vector<float> got(n);
    q.memcpy(got.data(), s.ym, n * 4).wait();
    size_t differ = 0, stray = 0;
    for (unsigned t = 0; t < MT; ++t)
        for (size_t i = 0; i < s.ys; ++i) {
            const float *g = &got[t * s.ys + i];
            if (i < s.k.rows) differ += std::memcmp(g, &s.ref[t * s.ys + i], 4) != 0;
            else {
                uint32_t u;
                std::memcpy(&u, g, 4);
                stray += u != 0xffffffffu;
            }
        }
    return !differ && !stray;
}
template <typename K, typename RW>
static double form(sycl::queue &q, Shape<K> &s, const RW &rw, const char *what, double base) {
    if (g_pcs) {
        for (unsigned rep = 0; rep < 300; ++rep) {
            flush(q, rep);
            launch(q, rw);
        }
        q.wait();
        std::printf("pcs ran %-22s %s\n", s.name, what);
        return 0;
    }
    const bool ok = same(q, s, rw);
    g_fail += !ok;
    const double us = med_us(q, rw, true);
    std::printf("%s %-22s %-14s | cold %7.1f us%s", ok ? "bitwise" : "DIFFERS", s.name, what, us, base > 0 ? "" : "\n");
    if (base > 0) std::printf(" (x%.3f)\n", base / us);
    std::fflush(stdout);
    return us;
}
template <unsigned G, unsigned R, typename K> static DenseRowsGR<K, G, R> gr(Shape<K> &s, size_t xs) {
    return {s.k, s.w, s.x, xs, s.ym, s.ys, MT, (MT + G - 1) / G};
}
template <unsigned G, typename K> static DenseRowsG<K, G> g1(Shape<K> &s, size_t xs) {
    return {s.k, s.w, s.x, xs, s.ym, s.ys, MT, (MT + G - 1) / G};
}

template <unsigned C, unsigned G, unsigned R, unsigned D, unsigned V, typename K> static auto vr(Shape<K> &s) {
    using QV = Q8V<C, D, V>;
    if constexpr (R == 1) return DenseRowsG<QV, G>{{s.k.rows, 0u}, s.w, s.x, s.xs, s.ym, s.ys, MT, (MT + G - 1) / G};
    else return DenseRowsGR<QV, G, R>{{s.k.rows, 0u}, s.w, s.x, s.xs, s.ym, s.ys, MT, (MT + G - 1) / G};
}
// the decode variants of one (G, R) form against its engine form's time
template <unsigned C, unsigned G, unsigned R, typename K> static void variants(sycl::queue &q, Shape<K> &s, const char *fr, double base) {
    char b[48];
    auto f = [&](auto rw, const char *v) { std::snprintf(b, sizeof b, "%s %s", fr, v); form(q, s, rw, b, base); };
    f(vr<C, G, R, 0, 0>(s), "D0V0");
    f(vr<C, G, R, 1, 0>(s), "D1V0");
    f(vr<C, G, R, 2, 0>(s), "D2V0");
    f(vr<C, G, R, 0, 1>(s), "D0V1");
    f(vr<C, G, R, 0, 2>(s), "D0V2");
    f(vr<C, G, R, 0, 3>(s), "D0V3");
    f(vr<C, G, R, 2, 1>(s), "D2V1");
    f(vr<C, G, R, 2, 2>(s), "D2V2");
    f(vr<C, G, R, 2, 3>(s), "D2V3");
}

template <unsigned C> static void run_shape(sycl::queue &q, unsigned rows, unsigned seed) {
    using K = GemvQ8P<C, ActF32>;
    constexpr unsigned cols = C * 32;
    Shape<K> s{};
    s.k.rows = rows;
    s.k.xn = 0;
    std::snprintf(s.name, sizeof s.name, "Q8_0 %ux%u", rows, cols);
    s.xs = (size_t)cols + 32;
    s.ys = rows + 8;
    const auto hw = packed_q8(cols, rows, seed);
    s.w = dev_copy(q, hw);
    s.x = dev_copy(q, rand_f(MT * s.xs, seed + 1, -2.0f, 2.0f));
    const size_t n = (size_t)MT * s.ys;
    s.yr = sycl::malloc_device<float>(n, q);
    s.ym = sycl::malloc_device<float>(n, q);
    q.memset(s.yr, 0xff, n * 4).wait();
    for (unsigned t = 0; t < MT; ++t) {
        const auto kk = s.k;
        const uint8_t *ww = s.w;
        const float *xx = s.x + t * s.xs;
        float *yy = s.yr + t * s.ys;
        q.parallel_for(sycl::nd_range<1>(((size_t)rows + 15) / 16 * 512, 512),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it, ww, xx, yy); });
    }
    q.wait();
    s.ref.resize(n);
    q.memcpy(s.ref.data(), s.yr, n * 4).wait();
    std::printf("-- %s: weights %.2f MB, %u x 16 = %.1f M weight-tokens\n", s.name, hw.size() / 1e6, rows * cols,
                (double)rows * cols * 16 / 1e6);
    const double wtok = (double)rows * cols * 16;
    double base;
    if (rows >= 4096) base = form(q, s, gr<4, 4>(s, s.xs), "engine G4 R4", 0);
    else base = form(q, s, g1<4>(s, s.xs), "engine G4", 0);
    if (g_pcs) return;
    std::printf("   engine form: %.2f T weight-tokens/s, weights %.0f GB/s\n", wtok / base * 1e-6, hw.size() / base * 1e-3);
    // diagnostics (not the engine's values)
    if (rows >= 4096) {
        std::printf("   diag warm %.1f us, x shared %.1f us\n", med_us(q, gr<4, 4>(s, s.xs), false),
                    med_us(q, gr<4, 4>(s, 0), true));
    } else {
        std::printf("   diag warm %.1f us, x shared %.1f us\n", med_us(q, g1<4>(s, s.xs), false), med_us(q, g1<4>(s, 0), true));
    }
    // round18 d1: the fastest (G, R) per shape (bitwise): 6144 x 1280 G8 R2 (x1.013) / G8 (x1.027), 1792 x 5120 G8 R2
    // (x1.135), 864 x 8192 G8 R2 (x1.278), 864 x 2304 G4 R2 (x1.109), 768 x 4096 G2 R4 (x1.088)
    if (rows >= 4096) variants<C, 4, 4>(q, s, "G4R4", base);
    else variants<C, 4, 1>(q, s, "G4", base);
    if constexpr (C == 40 || C == 160 || C == 256) variants<C, 8, 2>(q, s, "G8R2", base);
    if constexpr (C == 72) variants<C, 4, 2>(q, s, "G4R2", base);
    if constexpr (C == 128) variants<C, 2, 4>(q, s, "G2R4", base);
}

// Q6_K rows (the 13 Q6_K layers' attention matrices): the engine form against token groups of 8 and row blocks
template <unsigned NB> static void run_q6(sycl::queue &q, unsigned rows, unsigned seed) {
    using K = GemvQ6KP<NB, ActF32>;
    constexpr unsigned cols = NB * 256;
    Shape<K> s{};
    s.k.rows = rows;
    s.k.xn = 0;
    std::snprintf(s.name, sizeof s.name, "Q6_K %ux%u", rows, cols);
    s.xs = (size_t)cols + 32;
    s.ys = rows + 8;
    const auto hw = packed_q6k(cols, rows, seed);
    s.w = dev_copy(q, hw);
    s.x = dev_copy(q, rand_f(MT * s.xs, seed + 1, -2.0f, 2.0f));
    const size_t n = (size_t)MT * s.ys;
    s.yr = sycl::malloc_device<float>(n, q);
    s.ym = sycl::malloc_device<float>(n, q);
    q.memset(s.yr, 0xff, n * 4).wait();
    for (unsigned t = 0; t < MT; ++t) {
        const auto kk = s.k;
        const uint8_t *ww = s.w;
        const float *xx = s.x + t * s.xs;
        float *yy = s.yr + t * s.ys;
        q.parallel_for(sycl::nd_range<1>(((size_t)rows + 15) / 16 * 512, 512),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it, ww, xx, yy); });
    }
    q.wait();
    s.ref.resize(n);
    q.memcpy(s.ref.data(), s.yr, n * 4).wait();
    std::printf("-- %s: weights %.2f MB, %.1f M weight-tokens\n", s.name, hw.size() / 1e6, (double)rows * cols * 16 / 1e6);
    double base;
    if (rows >= 4096) base = form(q, s, gr<4, 4>(s, s.xs), "engine G4 R4", 0);
    else base = form(q, s, g1<4>(s, s.xs), "engine G4", 0);
    if (g_pcs) return;
    if (rows >= 4096) form(q, s, g1<4>(s, s.xs), "G4", base);
    form(q, s, g1<8>(s, s.xs), "G8", base);
    form(q, s, gr<4, 2>(s, s.xs), "G4 R2", base);
    if (rows < 4096) form(q, s, gr<4, 4>(s, s.xs), "G4 R4", base);
    form(q, s, gr<8, 2>(s, s.xs), "G8 R2", base);
    form(q, s, gr<2, 4>(s, s.xs), "G2 R4", base);
}

int main() {
    g_pcs = getenv("PCS") && atoi(getenv("PCS"));
    if (g_pcs && !pcs::begin()) return 2;
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const auto dev = q.get_device();
    std::printf("%s", dev.get_info<sycl::info::device::name>().c_str());
    if (dev.has(sycl::aspect::ext_intel_pci_address))
        std::printf(" %s", dev.get_info<sycl::ext::intel::info::device::pci_address>().c_str());
    std::printf("\n");
    g_flush = sycl::malloc_device<uint32_t>(FLUSH_WORDS, q);
    q.fill(g_flush, 0x01234567u, FLUSH_WORDS).wait();
    if (g_pcs) pcs::start();
    if (getenv("Q6_ONLY") && atoi(getenv("Q6_ONLY"))) goto q6;
    run_shape<40>(q, 6144, 11);  // query-b, 12 heads
    run_shape<160>(q, 1792, 12); // query-a 1280 + kv 512
    run_shape<256>(q, 864, 13);  // output-b
    run_shape<72>(q, 864, 14);   // shared-expert down
    run_shape<128>(q, 768, 15);  // output-a (half)
q6:
    run_q6<5>(q, 6144, 21);  // query-b, 12 heads
    run_q6<20>(q, 1792, 22); // query-a + kv
    run_q6<32>(q, 864, 23);  // output-b
    run_q6<16>(q, 768, 24);  // output-a (half)
    if (g_pcs) {
        pcs::stop_print("RowsP", 120, 16);
        return 0;
    }
    std::printf(g_fail ? "FAIL (%d forms differ)\n" : "PASS\n", g_fail);
    return g_fail ? 1 : 0;
}
