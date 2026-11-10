// Q6_K packed dense rows (GemvQ6KP) at the six-card shapes, cold (the matrix evicted before every launch, as in a
// decode step), against the bytes they read: the vocabulary head (5120 x 21547 rows per card, the guessing
// rounds' biggest single launch) and the Q6_K layers' q_b / output_a / output_b slices. Production forms:
// GemvQ6KP::row (one token), DenseRowsG<K, G> (token groups), DenseRowsGR<K, G, R> (R rows per sub-group).
// Candidate: Q6KAll<NB, G, R> = rowgr with every block's quant words loaded before the first product (the
// production form loads KSeg<NB> blocks at a time); same expressions in the same order, BITWISE against rowgr.
// Head only, the guessing rounds' 2/4/5/6-token blocks: the production token groups (OWN_MT_TGM 2:1, 4:2, 5:3,
// 6:3 with 4-row blocks) against all tokens in one group (rowg<M>, one read of the matrix), bitwise vs G1.
// HEAD_ONLY=1 skips the q_b / output_b shapes.
//
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_q6k_rows.cpp -o $S/bench_q6k_rows -lze_loader
//   LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib $S/bench_q6k_rows [CARD]
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

static constexpr unsigned MTMAX = 16, REPS = 12;
static constexpr size_t FLUSH_WORDS = (size_t)32 << 20; // 128 MiB
static uint32_t *g_flush = nullptr;
static int g_fail = 0;

// rowgr with all NB blocks' quant words loaded up front (registers: R * NB * 2 words per lane)
template <unsigned NB, unsigned NT, unsigned R> struct Q6KAll {
    unsigned rows, ng;
    const uint8_t *w;
    const float *x;
    size_t xs;
    float *y;
    size_t ys;
    unsigned mt;
    unsigned n() const { return (rows + R - 1) / R * ng; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned p) const {
        const unsigned r0 = p / ng * R, t0 = (p % ng) * NT;
        const float *xg = x + t0 * xs;
        float *yg = y + t0 * ys;
        const unsigned mg = mt - t0;
        constexpr size_t RB = ((size_t)NB * 210 + 15) & ~(size_t)15;
        constexpr unsigned NS = NB * 16, NSR = (NS + 31) / 32;
        const uint32_t *ql[R];
        const uint16_t *qh[R];
        float dbs[R][NSR];
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *rw = w + (size_t)(r0 + j < rows ? r0 + j : r0) * RB;
            ql[j] = reinterpret_cast<const uint32_t *>(rw);
            qh[j] = reinterpret_cast<const uint16_t *>(rw + (size_t)NB * 128);
            const int8_t *scl = reinterpret_cast<const int8_t *>(rw + (size_t)NB * 192);
            const uint16_t *dp = reinterpret_cast<const uint16_t *>(rw + (size_t)NB * 208);
#pragma unroll
            for (unsigned k = 0; k < NSR; ++k) {
                const unsigned si = 32 * k + lane < NS ? 32 * k + lane : NS - 1;
                dbs[j][k] = iq3::half(dp[si >> 4]) * float(int(scl[si]));
            }
        }
        uint32_t qa[R][NB], qb[R][NB];
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned b = 0; b < NB; ++b) {
                qa[j][b] = sg_bload(sg, ql[j] + (size_t)b * 32);
                qb[j][b] = qh[j][(size_t)b * 32 + lane];
            }
        float sum[R][NT];
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) sum[j][t] = 0;
#pragma unroll
        for (unsigned b = 0; b < NB; ++b) {
            sycl::vec<float, 8> xv[NT];
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) xv[t] = sg_bloadN<8>(sg, xg + t * xs + (size_t)b * 256);
#pragma unroll
            for (unsigned c = 0; c < 8; ++c) {
                const unsigned h = c >> 2, cc = c & 3u;
                const unsigned si = b * 16 + 2 * c;
#pragma unroll
                for (unsigned j = 0; j < R; ++j) {
                    const unsigned low = (qa[j][b] >> (8 * (2 * h + (cc & 1u)) + 4 * (cc >> 1))) & 15u;
                    const unsigned high = (qb[j][b] >> (8 * h + 2 * cc)) & 3u;
                    const float d0 = sycl::select_from_group(sg, dbs[j][si / 32], si % 32);
                    const float d1 = sycl::select_from_group(sg, dbs[j][si / 32], si % 32 + 1);
                    const float v = (lane < 16 ? d0 : d1) * float(int(low | (high << 4)) - 32);
#pragma unroll
                    for (unsigned t = 0; t < NT; ++t) sum[j][t] = sum[j][t] + v * xv[t][c];
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
                        if (t < mg) yg[t * ys + r0 + j] = sum[j][t];
        }
    }
};

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
// evict by READING 128 MiB (a written flush leaves dirty lines that are written back during the timed launch,
// round17 lesson); nothing is stored unless a word equals v, which the fill never holds
static void flush(sycl::queue &q, uint32_t v) {
    uint32_t *p = g_flush;
    q.parallel_for(sycl::nd_range<1>(FLUSH_WORDS / 64, 256), [=](sycl::nd_item<1> it) {
        const size_t i0 = it.get_global_linear_id() * 64;
        uint32_t s = 0;
        for (unsigned k = 0; k < 64; ++k) s ^= p[i0 + k];
        if (s == v + 0x9e3779b9u) p[0] = s;
    });
}
// as Backend41::launch_rows<0> / rows_launch: RowsP<D> in 512-item work-groups, 16 sub-groups each
template <typename D> static sycl::event go(sycl::queue &q, const D &d) {
    const RowsP<D> k{d};
    const size_t nwg = ((size_t)d.n() + 15) / 16;
    return q.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it); });
}
template <typename D> static double cold_us(sycl::queue &q, const D &d) {
    go(q, d).wait();
    double best = 1e30, sum = 0;
    for (unsigned i = 0; i < REPS; ++i) {
        flush(q, i);
        auto e = go(q, d);
        e.wait();
        const double t = ev_us(e);
        best = std::min(best, t);
        sum += t;
    }
    (void)best;
    return sum / REPS;
}
static std::vector<float> fetch(sycl::queue &q, const float *y, size_t n) {
    std::vector<float> h(n);
    q.memcpy(h.data(), y, n * 4).wait();
    return h;
}

template <unsigned NB> static void run(sycl::queue &q, const char *name, unsigned rows, unsigned seed, bool wide = false) {
    using K = GemvQ6KP<NB, ActF32>;
    constexpr size_t RB = ((size_t)NB * 210 + 15) & ~(size_t)15;
    const size_t cols = (size_t)NB * 256, wb = RB * rows;
    std::mt19937 rng(seed);
    std::vector<uint8_t> hw(wb);
    for (auto &b : hw) b = uint8_t(rng());
    for (unsigned r = 0; r < rows; ++r)
        for (unsigned b = 0; b < NB; ++b) {
            const uint16_t h = 0x1400 + (rng() & 0x3ff);
            std::memcpy(&hw[(size_t)r * RB + NB * 208 + 2 * b], &h, 2);
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
    const double gb = wb / 1e3; // bytes / 1e3 -> GB/s when divided by us
    std::printf("%s: %u rows x %zu columns, %.1f MB\n", name, rows, cols, wb / 1e6);

    // bitwise: candidates against the production forms, tokens 1 and 3 (and 2 for G = 2 groups)
    auto cmp = [&](const char *what, unsigned mt) {
        q.wait();
        const auto a = fetch(q, ya, ny), b = fetch(q, yb, ny);
        size_t bad = 0;
        for (unsigned t = 0; t < mt; ++t)
            for (unsigned r = 0; r < rows; ++r) bad += std::memcmp(&a[t * ys + r], &b[t * ys + r], 4) != 0;
        std::printf("  %s %s: %zu of %zu differ\n", bad ? "FAIL" : "PASS", what, bad, (size_t)mt * rows);
        g_fail += bad != 0;
    };
    for (unsigned mt : {1u, 3u}) {
        q.memset(ya, 0xff, ny * 4);
        q.memset(yb, 0xff, ny * 4).wait();
        if (mt == 1) go(q, DenseRowsG<K, 1>{k, w, x, xs, ya, ys, 1, 1});
        else go(q, DenseRowsG<K, 3>{k, w, x, xs, ya, ys, 3, 1});
        if (mt == 1) go(q, Q6KAll<NB, 1, 1>{rows, 1, w, x, xs, yb, ys, 1});
        else go(q, Q6KAll<NB, 3, 1>{rows, 1, w, x, xs, yb, ys, 3});
        cmp(mt == 1 ? "all-loads R1 vs rowg, 1 token" : "all-loads R1 vs rowg, 3 tokens", mt);
        q.memset(yb, 0xff, ny * 4).wait();
        if (mt == 1) go(q, Q6KAll<NB, 1, 2>{rows, 1, w, x, xs, yb, ys, 1});
        else go(q, Q6KAll<NB, 3, 2>{rows, 1, w, x, xs, yb, ys, 3});
        cmp(mt == 1 ? "all-loads R2 vs rowg, 1 token" : "all-loads R2 vs rowg, 3 tokens", mt);
        q.memset(yb, 0xff, ny * 4).wait();
        if (mt == 1) go(q, DenseRowsGR<K, 1, 4>{k, w, x, xs, yb, ys, 1, 1});
        else go(q, DenseRowsGR<K, 3, 4>{k, w, x, xs, yb, ys, 3, 1});
        cmp(mt == 1 ? "production rowgr R4 vs rowg, 1 token" : "production rowgr R4 vs rowg, 3 tokens", mt);
    }
    // cold timing (us, GB/s of weight bytes)
    auto line = [&](const char *what, double us) { std::printf("  %-34s %8.1f us %6.0f GB/s\n", what, us, gb / us); };
    std::printf(" one token:\n");
    line("row (DenseRowsG G1)", cold_us(q, DenseRowsG<K, 1>{k, w, x, xs, ya, ys, 1, 1}));
    line("rowgr R2", cold_us(q, DenseRowsGR<K, 1, 2>{k, w, x, xs, ya, ys, 1, 1}));
    line("rowgr R4 (production >= 4096 rows)", cold_us(q, DenseRowsGR<K, 1, 4>{k, w, x, xs, ya, ys, 1, 1}));
    line("all-loads R1", cold_us(q, Q6KAll<NB, 1, 1>{rows, 1, w, x, xs, yb, ys, 1}));
    line("all-loads R2", cold_us(q, Q6KAll<NB, 1, 2>{rows, 1, w, x, xs, yb, ys, 1}));
    std::printf(" three tokens:\n");
    line("rowg G3", cold_us(q, DenseRowsG<K, 3>{k, w, x, xs, ya, ys, 3, 1}));
    line("rowgr G3 R2", cold_us(q, DenseRowsGR<K, 3, 2>{k, w, x, xs, ya, ys, 3, 1}));
    line("rowgr G3 R4 (production)", cold_us(q, DenseRowsGR<K, 3, 4>{k, w, x, xs, ya, ys, 3, 1}));
    line("all-loads G3 R1", cold_us(q, Q6KAll<NB, 3, 1>{rows, 1, w, x, xs, yb, ys, 3}));
    line("all-loads G3 R2", cold_us(q, Q6KAll<NB, 3, 2>{rows, 1, w, x, xs, yb, ys, 3}));
    std::printf(" five tokens (groups of 3: two passes):\n");
    line("rowgr G3 R4 x2 (production)", cold_us(q, DenseRowsGR<K, 3, 4>{k, w, x, xs, ya, ys, 5, 2}));
    line("all-loads G3 R1 x2", cold_us(q, Q6KAll<NB, 3, 1>{rows, 2, w, x, xs, yb, ys, 5}));
    if (wide) { // the guessing rounds' M-token blocks: production token groups (OWN_MT_TGM, R4 rows) vs one group
        auto wide_m = [&](auto mc, auto gc) {
            constexpr unsigned M = decltype(mc)::value, GP = decltype(gc)::value, NGP = (M + GP - 1) / GP;
            q.memset(ya, 0xff, ny * 4);
            q.memset(yb, 0xff, ny * 4).wait();
            go(q, DenseRowsG<K, 1>{k, w, x, xs, ya, ys, M, M});
            go(q, DenseRowsG<K, M>{k, w, x, xs, yb, ys, M, 1});
            char what[96];
            std::snprintf(what, sizeof what, "one group G%u vs G1 x%u, %u tokens", M, M, M);
            cmp(what, M);
            q.memset(yb, 0xff, ny * 4).wait();
            go(q, Q6KAll<NB, M, 1>{rows, 1, w, x, xs, yb, ys, M});
            std::snprintf(what, sizeof what, "all-loads G%u vs G1 x%u, %u tokens", M, M, M);
            cmp(what, M);
            std::printf(" %u tokens:\n", M);
            std::snprintf(what, sizeof what, "rowgr G%u R4 x%u (production)", GP, NGP);
            line(what, cold_us(q, DenseRowsGR<K, GP, 4>{k, w, x, xs, ya, ys, M, NGP}));
            std::snprintf(what, sizeof what, "rowg G%u x%u (no row blocks)", GP, NGP);
            line(what, cold_us(q, DenseRowsG<K, GP>{k, w, x, xs, ya, ys, M, NGP}));
            std::snprintf(what, sizeof what, "rowg G%u x1 (one group)", M);
            line(what, cold_us(q, DenseRowsG<K, M>{k, w, x, xs, ya, ys, M, 1}));
            std::snprintf(what, sizeof what, "all-loads G%u x1", M);
            line(what, cold_us(q, Q6KAll<NB, M, 1>{rows, 1, w, x, xs, yb, ys, M}));
        };
        using I = std::integral_constant<unsigned, 1>;
        wide_m(std::integral_constant<unsigned, 2>{}, I{});
        wide_m(std::integral_constant<unsigned, 4>{}, std::integral_constant<unsigned, 2>{});
        wide_m(std::integral_constant<unsigned, 5>{}, std::integral_constant<unsigned, 3>{});
        wide_m(std::integral_constant<unsigned, 6>{}, std::integral_constant<unsigned, 3>{});
    }
    std::fflush(stdout);
    sycl::free(w, q);
    sycl::free(x, q);
    sycl::free(ya, q);
    sycl::free(yb, q);
}

int main(int argc, char **argv) {
    const int card = argc > 1 ? std::atoi(argv[1]) : 0;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const sycl::device dev = l0.at(card);
    const sycl::context ctx(dev);
    sycl::queue q(ctx, dev, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    std::printf("card %d %s\n", card, dev.get_info<sycl::info::device::name>().c_str());
    g_flush = sycl::malloc_device<uint32_t>(FLUSH_WORDS, q);
    q.memset(g_flush, 0, FLUSH_WORDS * 4).wait();
    const bool head_only = getenv("HEAD_ONLY") && atoi(getenv("HEAD_ONLY"));
    run<20>(q, "head (output.weight, card slice)", 21547, 1, true);
    if (!head_only) {
        run<5>(q, "q_b (Q6_K layers, two groups)", 8192, 2);
        run<32>(q, "output_b (Q6_K layers, card slice)", 864, 3);
    }
    sycl::free(g_flush, q);
    std::printf("%s\n", g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
