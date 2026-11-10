// Q8_0 packed dense rows (GemvQ8P::rowg, quant words per load segment from Q8Seg<C, NT>) at the six-card decode
// shapes, cold (the matrix evicted by READING 128 MiB before every launch), against Q8All<C, NT, SQ>: the same
// rowg with SQ words per segment (SQ = NQ: every quant word loaded before the first product). Same expressions in
// the same order: BITWISE against the production rowg. The second part (MT_ONLY=1 runs only it) times 2/4/5/6
// tokens grouped as the engine groups them (OWN_MT_TGM 2:1, 4:2, 5:3, 6:3).
// Run it on a 230 W card (tiles 1, 2, 4, 5 = 0000:23, 43, a3, e3): tiles 0 and 3 have a 275 W cap and do not show
// clock drops that a power-hungry form causes on the others (round18 e67/e68).
// Round18 e69pre (before Q8Seg took NT; data/dsv41-bringup-20261109/round18-e69pre-q8-rows*-bench.txt): every
// word first wins for groups of 3 on 32+ word rows (5 tokens: 5120 x 1024 24.0 -> 20.9 us, 8192 x 864 35.9 ->
// 29.2, 4096 x 864 19.9 -> 17.1) and groups of 2 on 40+ word rows, loses for 1 token (5120 x 1024 12.8 -> 26.3),
// 2304 columns and 2 tokens on 4096 columns; 2 tokens stay in groups of 1. Q8Seg<C, NT> now encodes that, so
// "production" below is the new rule for groups of 2 and 3.
//
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_q8_rows.cpp -o $S/bench_q8_rows -lze_loader
//   LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib $S/bench_q8_rows [CARD]
// Exit status 1 on any mismatch.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

static constexpr unsigned MTMAX = 8, REPS = 16;
static constexpr size_t FLUSH_WORDS = (size_t)32 << 20; // 128 MiB
static uint32_t *g_flush = nullptr;
static int g_fail = 0;

// GemvQ8P::rowg<NT> with SQ quant words per load segment (rows: one sub-group per row, as DenseRowsG<K, NT>)
template <unsigned C, unsigned NT, unsigned SQ> struct Q8All {
    unsigned rows, ng;
    const uint8_t *w;
    const float *x;
    size_t xs;
    float *y;
    size_t ys;
    unsigned mt;
    unsigned n() const { return rows * ng; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned p) const {
        const unsigned r = p / ng, t0 = (p % ng) * NT;
        constexpr unsigned NQ = C / 4, SEGQ = SQ, ND = (C + 31) / 32;
        static_assert(NQ % SEGQ == 0);
        constexpr size_t RB = ((size_t)C * 34 + 15) & ~(size_t)15;
        const uint8_t *rw = w + (size_t)r * RB;
        const float *xr = x + t0 * xs;
        float *yg = y + t0 * ys;
        const unsigned mg = mt - t0;
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(rw + (size_t)C * 32);
        float dv[ND];
#pragma unroll
        for (unsigned k = 0; k < ND; ++k) dv[k] = 32 * k + lane < C ? iq3::half(dp[32 * k + lane]) : 0.0f;
        const uint32_t *qw = reinterpret_cast<const uint32_t *>(rw);
        float sum[NT];
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NQ; s0 += SEGQ) {
            uint32_t q[SEGQ];
#pragma unroll
            for (unsigned m = 0; m < SEGQ; ++m) q[m] = sg_bload(sg, qw + (size_t)(s0 + m) * 32);
#pragma unroll
            for (unsigned m = 0; m < SEGQ; ++m) {
                sycl::vec<float, 4> xv[NT];
#pragma unroll
                for (unsigned t = 0; t < NT; ++t) xv[t] = sg_bloadN<4>(sg, xr + t * xs + (size_t)(s0 + m) * 128);
#pragma unroll
                for (unsigned k = 0; k < 4; ++k) {
                    const unsigned c = (s0 + m) * 4 + k;
                    const float d = sycl::select_from_group(sg, dv[c / 32], c % 32);
                    const float e = d * float(int8_t(uint8_t(q[m] >> (8 * k))));
#pragma unroll
                    for (unsigned t = 0; t < NT; ++t) sum[t] = sum[t] + e * xv[t][k];
                }
            }
        }
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = sg_tree32(sg, sum[t]);
        if (lane == 0) {
#pragma unroll
            for (unsigned t = 0; t < NT; ++t)
                if (t < mg) yg[t * ys + r] = sum[t];
        }
    }
};

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
static void flush(sycl::queue &q, uint32_t v) {
    uint32_t *p = g_flush;
    q.parallel_for(sycl::nd_range<1>(FLUSH_WORDS / 64, 256), [=](sycl::nd_item<1> it) {
        const size_t i0 = it.get_global_linear_id() * 64;
        uint32_t s = 0;
        for (unsigned k = 0; k < 64; ++k) s ^= p[i0 + k];
        if (s == v + 0x9e3779b9u) p[0] = s;
    });
}
template <typename D> static sycl::event go(sycl::queue &q, const D &d) {
    const RowsP<D> k{d};
    const size_t nwg = ((size_t)d.n() + 15) / 16;
    return q.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it); });
}
// mean of REPS cold launches (after 20 warm-up launches: the card's clock up)
template <typename D> static double cold_us(sycl::queue &q, const D &d) {
    for (int i = 0; i < 20; ++i) go(q, d);
    q.wait();
    double sum = 0;
    for (unsigned i = 0; i < REPS; ++i) {
        flush(q, i);
        auto e = go(q, d);
        e.wait();
        sum += ev_us(e);
    }
    return sum / REPS;
}
static std::vector<float> fetch(sycl::queue &q, const float *y, size_t n) {
    std::vector<float> h(n);
    q.memcpy(h.data(), y, n * 4).wait();
    return h;
}

template <unsigned C> static void run(sycl::queue &q, const char *name, unsigned rows, unsigned seed) {
    using K = GemvQ8P<C, ActF32>;
    constexpr unsigned NQ = C / 4;
    constexpr size_t RB = ((size_t)C * 34 + 15) & ~(size_t)15;
    const size_t cols = (size_t)C * 32, wb = RB * rows;
    std::mt19937 rng(seed);
    std::vector<uint8_t> hw(wb);
    for (auto &b : hw) b = uint8_t(rng());
    for (unsigned r = 0; r < rows; ++r)
        for (unsigned b = 0; b < C; ++b) {
            const uint16_t h = 0x1400 + (rng() & 0x3ff);
            std::memcpy(&hw[(size_t)r * RB + (size_t)C * 32 + 2 * b], &h, 2);
        }
    uint8_t *w = sycl::malloc_device<uint8_t>(wb, q);
    q.memcpy(w, hw.data(), wb).wait();
    const size_t xs = cols + 32, ys = rows + 8;
    std::uniform_real_distribution<float> u(-2.f, 2.f);
    std::vector<float> hx(MTMAX * xs);
    for (auto &v : hx) v = u(rng);
    float *x = sycl::malloc_device<float>(hx.size(), q);
    q.memcpy(x, hx.data(), hx.size() * 4).wait();
    const size_t ny = MTMAX * ys;
    float *ya = sycl::malloc_device<float>(ny, q), *yb = sycl::malloc_device<float>(ny, q);
    const K k{rows, 0};
    const double gb = wb / 1e3;
    std::printf("%s: %u rows x %zu columns, %.2f MB, %u quant words per lane (one-token segment %u)\n", name, rows,
                cols, wb / 1e6, NQ, Q8Seg<C>::v);
    auto cmp = [&](const char *what, unsigned mt) {
        q.wait();
        const auto a = fetch(q, ya, ny), b = fetch(q, yb, ny);
        size_t bad = 0;
        for (unsigned t = 0; t < mt; ++t)
            for (unsigned r = 0; r < rows; ++r) bad += std::memcmp(&a[t * ys + r], &b[t * ys + r], 4) != 0;
        std::printf("  %s %s: %zu of %zu differ\n", bad ? "FAIL" : "PASS", what, bad, (size_t)mt * rows);
        g_fail += bad != 0;
    };
    auto line = [&](const char *what, double us) { std::printf("  %-36s %8.2f us %6.0f GB/s\n", what, us, gb / us); };
    auto one = [&](auto ntc, auto sqc) {
        constexpr unsigned NT = decltype(ntc)::value, SQ = decltype(sqc)::value;
        q.memset(ya, 0xff, ny * 4);
        q.memset(yb, 0xff, ny * 4).wait();
        go(q, DenseRowsG<K, NT>{k, w, x, xs, ya, ys, NT, 1});
        go(q, Q8All<C, NT, SQ>{rows, 1, w, x, xs, yb, ys, NT});
        char what[96];
        std::snprintf(what, sizeof what, "segment %u vs production, %u token(s)", SQ, NT);
        cmp(what, NT);
        std::snprintf(what, sizeof what, "G%u production (segment %u)", NT, Q8Seg<C, NT>::v);
        line(what, cold_us(q, DenseRowsG<K, NT>{k, w, x, xs, ya, ys, NT, 1}));
        std::snprintf(what, sizeof what, "G%u segment %u", NT, SQ);
        line(what, cold_us(q, Q8All<C, NT, SQ>{rows, 1, w, x, xs, yb, ys, NT}));
    };
    using I1 = std::integral_constant<unsigned, 1>;
    using I2 = std::integral_constant<unsigned, 2>;
    using I3 = std::integral_constant<unsigned, 3>;
    using IA = std::integral_constant<unsigned, NQ>; // every word first
    using IS = std::integral_constant<unsigned, Q8Seg<C>::v>;
    if (!std::getenv("MT_ONLY")) {
        one(I1{}, IA{});
        one(I2{}, IA{});
        one(I3{}, IA{});
        if constexpr (NQ % 20 == 0 && NQ > 20) one(I1{}, std::integral_constant<unsigned, 20>{});
        if constexpr (NQ % 16 == 0 && NQ > 16) {
            one(I1{}, std::integral_constant<unsigned, 16>{});
            one(I3{}, std::integral_constant<unsigned, 16>{});
        }
    }
    // mt tokens the way the engine runs them (OWN_MT_TGM 2:1, 4:2, 5:3, 6:3: production groups of G, ng =
    // ceil(mt / G)) against Q8All in groups of GA with SQ words per segment
    auto mtarm = [&](unsigned mt, auto gc, auto gac, auto sqc) {
        constexpr unsigned G = decltype(gc)::value, GA = decltype(gac)::value, SQ = decltype(sqc)::value;
        const unsigned ng = (mt + G - 1) / G, nga = (mt + GA - 1) / GA;
        q.memset(ya, 0xff, ny * 4);
        q.memset(yb, 0xff, ny * 4).wait();
        go(q, DenseRowsG<K, G>{k, w, x, xs, ya, ys, mt, ng});
        go(q, Q8All<C, GA, SQ>{rows, nga, w, x, xs, yb, ys, mt});
        char what[96];
        std::snprintf(what, sizeof what, "%u tokens: groups of %u segment %u vs production", mt, GA, SQ);
        cmp(what, mt);
        std::snprintf(what, sizeof what, "M%u production groups of %u (seg %u)", mt, G, Q8Seg<C, G>::v);
        line(what, cold_us(q, DenseRowsG<K, G>{k, w, x, xs, ya, ys, mt, ng}));
        std::snprintf(what, sizeof what, "M%u groups of %u segment %u", mt, GA, SQ);
        line(what, cold_us(q, Q8All<C, GA, SQ>{rows, nga, w, x, xs, yb, ys, mt}));
    };
    mtarm(2, I1{}, I2{}, IS{});
    mtarm(2, I1{}, I2{}, IA{});
    mtarm(4, I2{}, I2{}, IA{});
    mtarm(5, I3{}, I3{}, IA{});
    mtarm(6, I3{}, I3{}, IA{});
    std::fflush(stdout);
    sycl::free(w, q);
    sycl::free(x, q);
    sycl::free(ya, q);
    sycl::free(yb, q);
}

int main(int argc, char **argv) {
    const int card = argc > 1 ? std::atoi(argv[1]) : 2;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const sycl::device dev = l0.at(card);
    const sycl::context ctx(dev);
    sycl::queue q(ctx, dev, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    std::printf("card %d %s (pci %s)\n", card, dev.get_info<sycl::info::device::name>().c_str(),
                dev.get_info<sycl::ext::intel::info::device::pci_address>().c_str());
    g_flush = sycl::malloc_device<uint32_t>(FLUSH_WORDS, q);
    q.memset(g_flush, 0, FLUSH_WORDS * 4).wait();
    // the six-card decode shapes (per card): q_a / shared gate+up (5120 columns), output_b (4096 / 8192
    // columns, 864 rows), the shared expert's down (2304 columns), q_b (1280 columns)
    run<160>(q, "5120 x 1024 (q_a, replicated)", 1024, 1);
    run<160>(q, "5120 x 384 (shared expert gate / up slice)", 384, 2);
    run<128>(q, "4096 x 864 (output_b slice)", 864, 3);
    run<256>(q, "8192 x 864 (output_b slice)", 864, 4);
    run<72>(q, "2304 x 864 (shared expert down slice)", 864, 5);
    run<40>(q, "1280 x 4096 (q_b, one group)", 4096, 6);
    sycl::free(g_flush, q);
    std::printf("%s\n", g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
