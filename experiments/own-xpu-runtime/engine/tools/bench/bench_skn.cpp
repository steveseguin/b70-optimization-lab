// skn-1 (2026-11-11), one card: the block path's per-token norm launches, production against the one-token path's
// one-work-group forms run per token (OWN_MT_SKNORM, sycl_v41.hpp "skn-1").
//
// Forms (production = what tpm_layer / tpm_head_all / tpm_publish launch today, rows_launch with OWN_MT_RWG = RWG):
//   N5   RowsP<TokRows<NormRows<5120, 4>>> (ff = OWN_NORM_FF: 1 and 0)      vs SkNormWM<5120, 16>      (bit 1)
//   ND   N5 + SkDotsWM<8> (two launches, OWN_MT_SKDOTS=8)                    vs SkNormDotsWM<8>         (bit 2)
//   NP   RowsP<RowsPair<TokRows<NormRows<1280, 4>>, TokRows<NormRows<512, 2>>>> vs SkNormPairWM         (bit 4)
//   CP   CompressPoolPM<ActF32> (ratio-2 pools)                              vs SkCompressPoolWM        (bit 8)
//   N512 RowsP<TokRows<NormRows<512, 2>>> (ratio-1 compressor norm)          vs SkNormWM<512, 2>        (bit 16)
// Bitwise: every m of MS, several input sets per m (real-like activations and weights, every smallk norm pattern
// incl. inf / NaN / subnormal / zero / tiny / huge, near-midpoint vectors that force the bracket's chain fallback on
// every token or on one token of the block); outputs memcmp'd over the whole buffer (tokens past m must stay
// untouched: 0xff fill). The dot partials of the fused launch against SkDotsWM's (the same code: equal bits), for
// several token shares (u0, nd) as OWN_MT_DSPLIT hands them.
// Timing (GPU time from profiling events, median of REPS): cold = 256 MiB read before every launch (or launch pair);
// warm = back-to-back launches on the same data (launch: median event time; chain: span of REPS launches / REPS).
// Two-launch forms (ND production): the span from the first launch's start to the second's end.
//   env MS=1,2,3,4,5,6,16,64,256 REPS=31 RWG=128 NOTIME=1 SEED=1
// build: icpx -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -fsycl-targets=intel_gpu_bmg_g31 \
//   -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" \
//   -Wno-deprecated-declarations -I /home/steve/dsv41-work/skn/engine/src bench_skn.cpp -o bench_skn
// run: ONEAPI_DEVICE_SELECTOR=level_zero:<N> ./bench_skn      Exit status 1 on any mismatch.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

static constexpr unsigned MMAX = 264, H = 5120, QR = 1280, HDIM = 512; // MMAX = the engine's MTA
static constexpr size_t H4 = 4 * (size_t)H, FS = 25 * 8;
static constexpr size_t FLUSH_WORDS = (size_t)64 << 20; // 256 MiB
static uint32_t *g_flush = nullptr;
static int g_fail = 0, g_reps = 31;
static unsigned g_rwg = 128;
static int g_order = 0; // ORDER=1: time the new form first

using N5 = NormRows<5120, 4>;
using N1 = NormRows<1280, 4>;
using N2 = NormRows<512, 2>;
using T5 = TokRows<N5>;
using T1 = TokRows<N1>;
using T2 = TokRows<N2>;
using TP = RowsPair<T1, T2>;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
static double span_us(const sycl::event &a, const sycl::event &b) {
    return (b.get_profiling_info<sycl::info::event_profiling::command_end>() -
            a.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
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
static void spin(sycl::queue &q, int n) {
    for (int i = 0; i < n; ++i) flush(q, 0x5a5a0000u + (uint32_t)i);
    q.wait();
}
// closed lever (bench only, skn-1 r2/r3: no gain at <= 30 slots, slower above): ExpertGroupM for blocks of up to 32 R slots on ONE sub-group, the ids in registers (lane l
// of round k holds slot l + 32 k) instead of local memory. Each slot runs ExpertGroupM's two scans in the same order
// with the same integer logic; the scanned values (ids, chunk counts) are broadcast from the lane that holds them
// instead of read from local memory, so every word written (grp[0], EXP / CNT per group, SLOT per member) is
// ExpertGroupM's, and no other word is written. ExpertGroupM's scans waited on one local-memory load per step
// (4.4 -> 6.9 us at 12 -> 30 slots in checks). launch_sg(c, 1, ExpertGroupSG<R>{nsl, cap, heavy}, ids, grp).
template <unsigned R> struct ExpertGroupSG {
    static constexpr unsigned SMAX = 32 * R;
    static_assert(R >= 1 && SMAX <= RUGrp::MAXU);
    unsigned nsl;
    unsigned cap = 16;
    bool heavy = false;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint32_t *ids, uint32_t *grp) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const unsigned cap = this->cap < 1 ? 1u : this->cap > RUGrp::CAP ? RUGrp::CAP : this->cap;
        const unsigned ns = nsl < SMAX ? nsl : SMAX;
        uint32_t le[R];
#pragma unroll
        for (unsigned k = 0; k < R; ++k) le[k] = lane + 32 * k < ns ? ids[lane + 32 * k] : 0u;
        auto id_at = [&](unsigned j) { // slot j's id (j uniform)
            uint32_t v = 0;
#pragma unroll
            for (unsigned k = 0; k < R; ++k)
                if (j / 32 == k) v = sycl::select_from_group(sg, le[k], j % 32);
            return v;
        };
        unsigned before[R], head[R], lc[R];
#pragma unroll
        for (unsigned k = 0; k < R; ++k) {
            const unsigned s = lane + 32 * k;
            before[k] = 0;
            head[k] = s;
            lc[k] = 0;
            const uint32_t e = le[k];
            unsigned bf = 0, total = 0, hd = s;
            for (unsigned j = 0; j < ns; ++j) { // ExpertGroupM's first scan
                const bool eq = id_at(j) == e;
                if (eq && j < s) {
                    if (bf % cap == 0) hd = j;
                    ++bf;
                }
                total += eq ? 1u : 0u;
            }
            if (s >= ns) continue;
            if (bf % cap == 0) hd = s;
            const unsigned left = total - bf;
            lc[k] = bf % cap == 0 ? (left < cap ? left : cap) : 0u;
            before[k] = bf;
            head[k] = hd;
        }
        auto lc_at = [&](unsigned j) {
            unsigned v = 0;
#pragma unroll
            for (unsigned k = 0; k < R; ++k)
                if (j / 32 == k) v = sycl::select_from_group(sg, lc[k], j % 32);
            return v;
        };
        unsigned lr[R], mine = 0;
#pragma unroll
        for (unsigned k = 0; k < R; ++k) {
            const unsigned s = lane + 32 * k, n = lc[k];
            unsigned rank = 0;
            for (unsigned j = 0; j < ns; ++j) { // ExpertGroupM's second scan
                const unsigned cj = lc_at(j);
                rank += heavy ? (unsigned)(cj > n) | ((unsigned)(cj == n) & (unsigned)(j < s))
                              : (unsigned)(cj != 0) & (unsigned)(j < s);
            }
            lr[k] = rank;
            mine += (s < ns && n != 0) ? 1u : 0u;
        }
        const unsigned nu = sycl::reduce_over_group(sg, mine, sycl::plus<unsigned>());
#pragma unroll
        for (unsigned k = 0; k < R; ++k) {
            const unsigned s = lane + 32 * k, hd = head[k];
            unsigned u = 0; // lr[head]: the head's rank, from the lane that holds the head slot (lane-varying source)
#pragma unroll
            for (unsigned k2 = 0; k2 < R; ++k2) {
                const unsigned v = sycl::select_from_group(sg, lr[k2], hd % 32);
                if (hd / 32 == k2) u = v;
            }
            if (s >= ns) continue;
            const unsigned i = before[k] % cap;
            grp[RUGrp::SLOT + u * RUGrp::CAP + i] = s;
            if (i == 0) {
                grp[RUGrp::EXP + u] = le[k];
                grp[RUGrp::CNT + u] = lc[k];
            }
        }
        if (lane == 0) grp[0] = nu;
    }
};

// ExpertGroupM as the backend launches it (launch_local<LM>(items(nsl))) and ExpertGroupSG<R> (launch_sg, R by nsl)
static sycl::event eg_prod(sycl::queue &q, unsigned nsl, unsigned cap, bool heavy, const uint32_t *ids, uint32_t *grp) {
    ExpertGroupM k{nsl, cap};
    k.heavy = heavy;
    const size_t it_ = ExpertGroupM::items(nsl);
    return q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<float, 1> lt(ExpertGroupM::LM, hh);
        hh.parallel_for(sycl::nd_range<1>(it_, it_), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, ids, grp, &lt[0]); });
    });
}
template <unsigned R> static sycl::event eg_sg_r(sycl::queue &q, unsigned nsl, unsigned cap, bool heavy, const uint32_t *ids, uint32_t *grp) {
    const ExpertGroupSG<R> k{nsl, cap, heavy};
    return q.parallel_for(sycl::nd_range<1>(32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, ids, grp); });
}
static sycl::event eg_sg(sycl::queue &q, unsigned nsl, unsigned cap, bool heavy, const uint32_t *ids, uint32_t *grp) {
    if (nsl <= 32) return eg_sg_r<1>(q, nsl, cap, heavy, ids, grp);
    if (nsl <= 64) return eg_sg_r<2>(q, nsl, cap, heavy, ids, grp);
    return eg_sg_r<4>(q, nsl, cap, heavy, ids, grp);
}
// rows_launch (backend_sycl_v41_mt.inc): one sub-group per work-group up to OWN_MT_RWG rows, else 512 items
template <typename RW> static sycl::event rows(sycl::queue &q, const RW &rw) {
    const RowsP<RW> kr{rw};
    const size_t n = rw.n(), wg = n <= g_rwg ? 32 : 512, per = wg / 32, nwg = (n + per - 1) / per;
    return q.parallel_for(sycl::nd_range<1>(nwg * wg, wg), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kr(it); });
}
// launch_wgl (32-bit local words) and launch_wgs (float local), as the backend's
template <size_t SLM, typename K, typename... A> static sycl::event wgl(sycl::queue &q, size_t groups, size_t wg, K k, A... args) {
    return q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<uint32_t, 1> lt(SLM, hh);
        hh.parallel_for(sycl::nd_range<1>(groups * wg, wg), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            k(it, args..., &lt[0]);
        });
    });
}
template <size_t SLM, typename K, typename... A> static sycl::event wgs(sycl::queue &q, size_t groups, size_t wg, K k, A... args) {
    return q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<float, 1> lt(SLM, hh);
        hh.parallel_for(sycl::nd_range<1>(groups * wg, wg), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            k(it, args..., &lt[0]);
        });
    });
}

// ------------------------------------------------------------------------------------------------ host data
static std::mt19937 rng(20261111);
static std::normal_distribution<float> nd01(0.f, 1.f);
// near-midpoint vectors (bench_smallk's tune_mid): x[i0], x[i1] tuned so that D = 1 / sqrt(acc / N + 1e-20) lies at
// a float midpoint times (1 + off); off = 0 forces every bracket to fail
static void tune_mid(float *x, unsigned N, double off, int spread) {
    std::uniform_int_distribution<int> ue(-spread, spread);
    std::uniform_int_distribution<unsigned> ui(0, N - 1);
    for (unsigned i = 0; i < N; ++i) x[i] = nd01(rng) * std::ldexp(1.0f, ue(rng));
    unsigned i0 = ui(rng), i1 = ui(rng);
    while (i1 == i0) i1 = ui(rng);
    x[i0] = 0;
    x[i1] = 0;
    long double s0 = 0;
    for (unsigned i = 0; i < N; ++i) s0 += (long double)x[i] * x[i];
    const long double acc_g = s0 * 1.25L;
    const float f = (float)(1.0L / sqrtl(acc_g / N + 1e-20L));
    const long double mid = ((long double)f + (long double)std::nextafter(f, INFINITY)) / 2;
    const long double Dt = mid * (1.0L + off);
    const long double acc_t = N * (1.0L / (Dt * Dt) - 1e-20L);
    const long double need = acc_t - s0;
    if (need <= 0) return;
    float x0 = (float)sqrtl(need);
    while ((long double)x0 * x0 > need) x0 = std::nextafter(x0, 0.0f);
    const long double r1 = need - (long double)x0 * x0;
    const float x1 = (float)sqrtl(r1);
    x[i0] = (ui(rng) & 1) ? x0 : -x0;
    x[i1] = (ui(rng) & 1) ? x1 : -x1;
}
// norm input patterns (bench_smallk's 19 + real-like residual streams), N elements
static constexpr int NKIND = 20, K_REAL = 19, K_FORCE = 11;
static void fill_norm(float *x, unsigned N, int kind, unsigned v) {
    std::uniform_int_distribution<int> u8(-8, 8), u28(-28, 28);
    std::uniform_int_distribution<unsigned> ui(0, N - 1);
    switch (kind) {
    case 0: for (unsigned i = 0; i < N; ++i) x[i] = nd01(rng) * std::ldexp(1.0f, u8(rng)); break;
    case 1: for (unsigned i = 0; i < N; ++i) x[i] = nd01(rng) * std::ldexp(1.0f, u28(rng)); break;
    case 2: for (unsigned i = 0; i < N; ++i) x[i] = (ui(rng) < N / 100) ? nd01(rng) : 0.0f; break;
    case 3: for (unsigned i = 0; i < N; ++i) x[i] = nd01(rng) * 1e-3f; x[ui(rng)] = 300.0f; break;
    case 4: { const float c = 1.0f + (float)v * 1.37e-5f; for (unsigned i = 0; i < N; ++i) x[i] = c; } break;
    case 5: for (unsigned i = 0; i < N; ++i) x[i] = (i & 1) ? -0.0f : 0.0f; break;
    case 6: for (unsigned i = 0; i < N; ++i) x[i] = nd01(rng) * 1e-16f; break;
    case 7: for (unsigned i = 0; i < N; ++i) x[i] = nd01(rng) * 1e15f; break;
    case 8: for (unsigned i = 0; i < N; ++i) x[i] = nd01(rng); x[ui(rng)] = (v & 1) ? INFINITY : -INFINITY; break;
    case 9: for (unsigned i = 0; i < N; ++i) x[i] = nd01(rng); x[ui(rng)] = NAN; break;
    case 10: for (unsigned i = 0; i < N; ++i) x[i] = (i & 1) ? nd01(rng) * 1e-39f : nd01(rng) * 1e-12f; break;
    case 11: tune_mid(x, N, 0.0, 6); break;
    case 12: tune_mid(x, N, (v & 1) ? 1e-13 : -1e-13, 6); break;
    case 13: tune_mid(x, N, (v & 1) ? 1e-12 : -1e-12, 6); break;
    case 14: tune_mid(x, N, (v & 1) ? 3e-12 : -3e-12, 6); break;
    case 15: tune_mid(x, N, (v & 1) ? 5e-12 : -5e-12, 6); break;
    case 16: tune_mid(x, N, (v & 1) ? 1e-11 : -1e-11, 6); break;
    case 17: tune_mid(x, N, ((v & 1) ? 4e-12 : -4e-12) * (1.0 + 1e-3 * (double)((int)(v % 41) - 20)), 6); break;
    case 18:
        for (unsigned i = 0; i < N; ++i) x[i] = nd01(rng) * 0.05f;
        for (int k = 0; k < 6; ++k) x[ui(rng)] = nd01(rng) * 40.0f;
        break;
    default: { // real-like residual stream: log-normal channel scales, a few fixed massive channels, token jitter
        std::mt19937 cr(77 + N); // channel profile fixed per width (as a model's)
        std::normal_distribution<float> cn(0.f, 1.f);
        for (unsigned i = 0; i < N; ++i) {
            const float sc = 0.08f * std::exp(0.7f * cn(cr));
            x[i] = nd01(rng) * sc;
        }
        for (unsigned k = 0; k < 4; ++k) x[(k * 977u + 13u) % N] = (k & 1 ? -1.f : 1.f) * (60.f + 30.f * nd01(rng));
        break;
    }
    }
}
// is token x's scale forced onto the chain (exact D within 3e-12 of a float midpoint: no bracket passes)?
static bool forced(const float *x, unsigned N) {
    long double s = 0;
    for (unsigned i = 0; i < N; ++i) {
        if (!std::isfinite(x[i])) return false;
        s += (long double)x[i] * x[i];
    }
    const long double D = 1.0L / sqrtl(s / N + 1e-20L);
    const float f = (float)D;
    const long double up = ((long double)f + std::nextafter(f, INFINITY)) / 2, dn = ((long double)f + std::nextafter(f, 0.0f)) / 2;
    const long double d = std::min(fabsl(D - up), fabsl(D - dn)) / D;
    return s > 1e-25L && s < 1e30L && d < 3e-12L;
}
static std::vector<float> weights(unsigned N, unsigned seed) { // real-like norm weights
    std::mt19937 r(seed);
    std::normal_distribution<float> n(0.f, 1.f);
    std::vector<float> w(N);
    for (unsigned i = 0; i < N; ++i) w[i] = 1.0f + 0.3f * n(r);
    for (unsigned k = 0; k < 8; ++k) w[(k * 619u + 5u) % N] = 4.0f + n(r);
    w[N / 3] = 0.0f;
    w[N / 2] = -0.25f;
    return w;
}
// a block's tokens: set s of m tokens, width N (stride N), kind per token
static int kind_of(int set, unsigned t, unsigned m) {
    switch (set) {
    case 0: return K_REAL;                          // real-like
    case 1: return 18;                              // smallk's real-ish (outliers)
    case 2: return (int)(t % NKIND);                // every pattern, cycling over the tokens
    case 3: return (int)((t * 7 + 3) % NKIND);      // ... shifted
    case 4: return K_FORCE;                         // every token forced onto the chain
    case 5: return t == m / 2 ? K_FORCE : K_REAL;   // one forced token in a real-like block
    case 6: return 12 + (int)(t % 6);               // near-midpoint at 1e-13 .. 1e-11
    default: return t == 0 ? 9 : (t == m - 1 ? 8 : K_REAL); // NaN first, inf last
    }
}
static constexpr int NSET = 8;
static const char *set_name(int s) {
    static const char *n[] = {"real-like", "real-ish outliers", "all patterns", "all patterns (shifted)",
                              "all forced", "one forced", "near-midpoint", "NaN / inf ends"};
    return n[s];
}
static void fill_block(std::vector<float> &h, unsigned N, unsigned m, int set, unsigned &nforced) {
    h.assign((size_t)MMAX * N, 0.0f);
    for (unsigned t = 0; t < MMAX; ++t) fill_norm(h.data() + (size_t)t * N, N, t < m ? kind_of(set, t, m) : K_REAL, t * 31 + (unsigned)set);
    nforced = 0;
    for (unsigned t = 0; t < m; ++t) nforced += forced(h.data() + (size_t)t * N, N);
}

// ids for nsl slots (6 per token): pattern 0 real-like (per token 6 distinct of 256, a few hot experts), 1 of 8
// experts (distinct per token), 2 of 3 experts with repeats inside a token, 3 one expert for every slot, 4 all distinct
static std::vector<uint32_t> eg_ids(unsigned nsl, int pat) {
    std::vector<uint32_t> v(nsl);
    std::uniform_int_distribution<unsigned> u256(0, 255), hot(0, 11);
    for (unsigned t = 0; t * 6 < nsl; ++t) {
        std::vector<uint32_t> tok;
        while (tok.size() < 6) {
            uint32_t e;
            switch (pat) {
            case 0: e = (rng() & 1) ? hot(rng) * 17 % 256 : u256(rng); break;
            case 1: e = rng() % 8; break;
            case 2: e = rng() % 3; tok.push_back(e); continue;
            case 3: e = 42; tok.push_back(e); continue;
            default: e = (t * 6 + (unsigned)tok.size()) % 256; tok.push_back(e); continue;
            }
            if (std::find(tok.begin(), tok.end(), e) == tok.end()) tok.push_back(e);
        }
        for (unsigned k = 0; k < 6 && t * 6 + k < nsl; ++k) v[t * 6 + k] = tok[k];
    }
    return v;
}
template <typename T> static T *dalloc(sycl::queue &q, size_t n) { return sycl::malloc_device<T>(n, q); }
template <typename T> static void up(sycl::queue &q, T *d, const std::vector<T> &h) { q.memcpy(d, h.data(), h.size() * sizeof(T)).wait(); }
template <typename T> static std::vector<T> down(sycl::queue &q, const T *d, size_t n) {
    std::vector<T> h(n);
    q.memcpy(h.data(), d, n * sizeof(T)).wait();
    return h;
}
template <typename T> static bool same(const std::vector<T> &a, const std::vector<T> &b) {
    return a.size() == b.size() && !std::memcmp(a.data(), b.data(), a.size() * sizeof(T)); // bit patterns (NaN too)
}
static void report(bool ok, const char *what, unsigned m, const char *extra = "") {
    if (!ok || getenv("VERBOSE")) std::printf("%s m=%-3u %s%s\n", ok ? "bitwise" : "DIFFERS", m, what, extra);
    std::fflush(stdout);
    g_fail += !ok;
}

// ------------------------------------------------------------------------------------------------ timing
struct Tm {
    double cold, warm, chain;
};
// f() submits the form's launches and returns {first, last} events
static Tm timeit(sycl::queue &q, const std::function<std::pair<sycl::event, sycl::event>()> &f) {
    for (int i = 0; i < 3; ++i) f();
    q.wait();
    std::vector<double> c, w;
    for (int r = 0; r < g_reps; ++r) {
        flush(q, (uint32_t)r);
        const auto e = f();
        q.wait();
        c.push_back(span_us(e.first, e.second));
    }
    for (int i = 0; i < 3; ++i) f();
    q.wait();
    std::vector<std::pair<sycl::event, sycl::event>> es;
    for (int r = 0; r < g_reps; ++r) es.push_back(f());
    q.wait();
    for (auto &e : es) w.push_back(span_us(e.first, e.second));
    const double ch = span_us(es.front().first, es.back().second) / g_reps;
    std::sort(c.begin(), c.end());
    std::sort(w.begin(), w.end());
    return {c[c.size() / 2], w[w.size() / 2], ch};
}
static std::pair<sycl::event, sycl::event> one(sycl::event e) { return {e, e}; }

int main() {
    std::vector<unsigned> ms{1, 2, 3, 4, 5, 6, 16, 64, 256};
    if (const char *e = getenv("MS")) {
        ms.clear();
        for (const char *s = e; *s;) {
            ms.push_back((unsigned)atoi(s));
            const char *c = std::strchr(s, ',');
            if (!c) break;
            s = c + 1;
        }
    }
    if (const char *e = getenv("REPS")) g_reps = std::max(1, atoi(e));
    if (const char *e = getenv("RWG")) g_rwg = (unsigned)atoi(e);
    if (const char *e = getenv("ORDER")) g_order = atoi(e);
    const bool notime = getenv("NOTIME") && atoi(getenv("NOTIME")) != 0;
    const unsigned seed = getenv("SEED") ? (unsigned)atoi(getenv("SEED")) : 1u;
    rng.seed(20261111u + seed);
    sycl::queue q{sycl::gpu_selector_v, sycl::property_list{sycl::property::queue::in_order{},
                                                            sycl::property::queue::enable_profiling{}}};
    std::printf("device: %s; OWN_MT_RWG=%u; seed %u\n", q.get_device().get_info<sycl::info::device::name>().c_str(), g_rwg, seed);
    g_flush = dalloc<uint32_t>(q, FLUSH_WORDS);
    q.memset(g_flush, 0, FLUSH_WORDS * 4).wait();
    // buffers: MMAX tokens of each (the block buffers hold MTA tokens)
    float *x = dalloc<float>(q, (size_t)MMAX * H), *ya = dalloc<float>(q, (size_t)MMAX * H), *yb = dalloc<float>(q, (size_t)MMAX * H);
    float *st = dalloc<float>(q, (size_t)MMAX * H4), *fn = dalloc<float>(q, 24 * H4);
    double *da = dalloc<double>(q, (size_t)MMAX * FS), *db = dalloc<double>(q, (size_t)MMAX * FS);
    float *qa = dalloc<float>(q, (size_t)MMAX * QR), *kv = dalloc<float>(q, (size_t)MMAX * HDIM);
    float *qna = dalloc<float>(q, (size_t)MMAX * QR), *qnb = dalloc<float>(q, (size_t)MMAX * QR);
    float *kna = dalloc<float>(q, (size_t)MMAX * HDIM), *knb = dalloc<float>(q, (size_t)MMAX * HDIM);
    float *mkv = dalloc<float>(q, (size_t)(MMAX + 1) * HDIM), *msc = dalloc<float>(q, (size_t)(MMAX + 1) * HDIM);
    float *st2 = dalloc<float>(q, (size_t)MMAX * H4), *hpost = dalloc<float>(q, (size_t)MMAX * 4),
          *hcomb = dalloc<float>(q, (size_t)MMAX * 16), *hmix = dalloc<float>(q, (size_t)MMAX * 4),
          *hpre = dalloc<float>(q, (size_t)MMAX * 4), *hpd = dalloc<float>(q, (size_t)MMAX * 4);
    {
        std::normal_distribution<float> n(0.f, 1.f);
        std::vector<float> a((size_t)MMAX * 4), c((size_t)MMAX * 16), mx((size_t)MMAX * 4);
        for (auto &v : a) v = 2.0f / (1.0f + std::exp(-n(rng)));
        for (auto &v : c) v = std::fabs(n(rng)) * 0.25f;
        for (auto &v : mx) v = 1.0f / (1.0f + std::exp(-n(rng))) + 1e-6f;
        up(q, hpost, a), up(q, hcomb, c), up(q, hmix, mx), up(q, hpre, mx);
    }
    uint32_t *egi = dalloc<uint32_t>(q, 6 * MMAX), *ega = dalloc<uint32_t>(q, RUGrp::WORDS), *egb = dalloc<uint32_t>(q, RUGrp::WORDS);
    float *w5 = dalloc<float>(q, H), *wq = dalloc<float>(q, QR), *wk = dalloc<float>(q, HDIM), *wc = dalloc<float>(q, HDIM);
    up(q, w5, weights(H, seed + 1));
    up(q, wq, weights(QR, seed + 2));
    up(q, wk, weights(HDIM, seed + 3));
    up(q, wc, weights(HDIM, seed + 4));
    { // streams (real-ish: 4 x 5120 per token) and fn rows (24 x 20480)
        std::vector<float> h((size_t)MMAX * H4), f((size_t)24 * H4);
        for (unsigned t = 0; t < MMAX; ++t)
            for (unsigned s = 0; s < 4; ++s) fill_norm(h.data() + t * H4 + s * H, H, (t + s) % 3 ? K_REAL : 18, t * 4 + s);
        h[(size_t)7 * H4 + 11] = NAN; // a NaN stream value in token 7, an inf in token 9 (the dots' NaN path)
        h[(size_t)9 * H4 + 5000] = INFINITY;
        std::normal_distribution<float> n(0.f, 0.02f);
        for (auto &v : f) v = n(rng);
        up(q, st, h);
        up(q, fn, f);
    }
    auto sent = [&](void *p, size_t bytes) { q.memset(p, 0xff, bytes).wait(); };

    // ---------------------------------------------------------------- bitwise
    size_t nchk = 0, nforced_tot = 0;
    for (const unsigned m : ms) {
        if (m < 1 || m > MMAX - 8) { std::printf("m=%u: outside 1..%u\n", m, MMAX - 8); return 2; }
        size_t forced5 = 0, forcedp = 0, forcedc = 0;
        for (int set = 0; set < NSET; ++set) {
            char ex[160];
            // N5 / ND
            std::vector<float> hx;
            unsigned nf = 0;
            fill_block(hx, H, m, set, nf);
            forced5 += nf;
            up(q, x, hx);
            std::vector<float> ref;
            for (int ff = 1; ff >= 0; --ff) {
                sent(ya, (size_t)MMAX * H * 4);
                rows(q, T5{N5{x, w5, ya, ff != 0}, m, {H, H, 0, 0}}).wait();
                auto r = down(q, ya, (size_t)MMAX * H);
                if (ff) ref = r;
                else report(same(r, ref), "N5 production ff=0 vs ff=1", m);
            }
            sent(yb, (size_t)MMAX * H * 4);
            wgl<32>(q, m, 512, SkNormWM<5120, 16>{m, H, H}, (const float *)x, (const float *)w5, yb).wait();
            std::snprintf(ex, sizeof ex, " [%s; %u forced tokens]", set_name(set), nf);
            report(same(down(q, yb, (size_t)MMAX * H), ref), "SkNormWM<5120,16> vs N5", m, ex);
            ++nchk;
            // fused: token shares (u0, nd) as skmix hands them (all, none, the last one, a middle share)
            const unsigned shares[4][2] = {{0, m}, {0, 0}, {m - 1, 1}, {m / 3, (m + 1) / 2}};
            for (const auto &sh : shares) {
                const unsigned u0 = sh[0], nt = std::min(sh[1], m - u0);
                const float *sv = st + (size_t)u0 * H4;
                double *oa = da + (size_t)u0 * FS, *ob = db + (size_t)u0 * FS;
                sent(ya, (size_t)MMAX * H * 4), sent(yb, (size_t)MMAX * H * 4);
                sent(da, (size_t)MMAX * FS * 8), sent(db, (size_t)MMAX * FS * 8);
                rows(q, T5{N5{x, w5, ya}, m, {H, H, 0, 0}});
                if (nt) wgl<64>(q, (size_t)nt * 25, 512, SkDotsWM<8>{nt, H4, FS}, sv, (const float *)fn, oa);
                q.wait();
                wgl<64>(q, m + (size_t)nt * 25, 512, SkNormDotsWM<8>{m, nt, H, H, H4, FS}, (const float *)x,
                        (const float *)w5, yb, sv, (const float *)fn, ob).wait();
                const bool y_ok = same(down(q, yb, (size_t)MMAX * H), down(q, ya, (size_t)MMAX * H));
                const bool d_ok = same(down(q, db, (size_t)MMAX * FS), down(q, da, (size_t)MMAX * FS));
                std::snprintf(ex, sizeof ex, " [%s; dots of tokens %u..%u]", set_name(set), u0, u0 + nt);
                report(y_ok, "SkNormDotsWM<8> norm vs N5", m, ex);
                report(d_ok, "SkNormDotsWM<8> partials vs SkDotsWM<8>", m, ex);
                nchk += 2;
                // <4>
                sent(da, (size_t)MMAX * FS * 8), sent(db, (size_t)MMAX * FS * 8);
                if (nt) wgl<64>(q, (size_t)nt * 25, 512, SkDotsWM<4>{nt, H4, FS}, sv, (const float *)fn, oa);
                wgl<64>(q, m + (size_t)nt * 25, 512, SkNormDotsWM<4>{m, nt, H, H, H4, FS}, (const float *)x,
                        (const float *)w5, yb, sv, (const float *)fn, ob).wait();
                report(same(down(q, db, (size_t)MMAX * FS), down(q, da, (size_t)MMAX * FS)) &&
                           same(down(q, yb, (size_t)MMAX * H), down(q, ya, (size_t)MMAX * H)),
                       "SkNormDotsWM<4> vs N5 + SkDotsWM<4>", m, ex);
                ++nchk;
            }
            // NP: q_a 1280 + kv 512
            std::vector<float> hq, hk;
            unsigned nfq = 0, nfk = 0;
            fill_block(hq, QR, m, set, nfq);
            fill_block(hk, HDIM, m, (set + 3) % NSET, nfk);
            forcedp += nfq + nfk;
            up(q, qa, hq);
            up(q, kv, hk);
            std::vector<float> rq, rk;
            for (int ff = 1; ff >= 0; --ff) {
                sent(qna, (size_t)MMAX * QR * 4), sent(kna, (size_t)MMAX * HDIM * 4);
                rows(q, TP{T1{N1{qa, wq, qna, ff != 0}, m, {QR, QR, 0, 0}}, T2{N2{kv, wk, kna, ff != 0}, m, {HDIM, HDIM, 0, 0}}}).wait();
                auto a = down(q, qna, (size_t)MMAX * QR), b = down(q, kna, (size_t)MMAX * HDIM);
                if (ff) rq = a, rk = b;
                else report(same(a, rq) && same(b, rk), "NP production ff=0 vs ff=1", m);
            }
            sent(qnb, (size_t)MMAX * QR * 4), sent(knb, (size_t)MMAX * HDIM * 4);
            wgl<16>(q, m, 256, SkNormPairWM{m, QR, QR, HDIM, HDIM}, (const float *)qa, (const float *)wq, qnb,
                    (const float *)kv, (const float *)wk, knb).wait();
            std::snprintf(ex, sizeof ex, " [%s; forced: %u q_a, %u kv]", set_name(set), nfq, nfk);
            report(same(down(q, qnb, (size_t)MMAX * QR), rq) && same(down(q, knb, (size_t)MMAX * HDIM), rk),
                   "SkNormPairWM vs NP", m, ex);
            ++nchk;
            // N512 (compressor ratio 1): kv-shaped tokens into kna / knb
            sent(kna, (size_t)MMAX * HDIM * 4), sent(knb, (size_t)MMAX * HDIM * 4);
            rows(q, T2{N2{kv, wc, kna}, m, {HDIM, HDIM, 0, 0}}).wait();
            wgl<4>(q, m, 64, SkNormWM<512, 2>{m, HDIM, HDIM}, (const float *)kv, (const float *)wc, knb).wait();
            report(same(down(q, knb, (size_t)MMAX * HDIM), down(q, kna, (size_t)MMAX * HDIM)), "SkNormWM<512,2> vs N512", m, ex);
            ++nchk;
            // CP: ratio-2 pools of rows t, t + 1 (t = t0 + 2 g), both parities of the block's first position
            for (unsigned t0 = 0; t0 < 2; ++t0) {
                const unsigned np = t0 < m ? (m - t0 + 1) / 2 : 0;
                if (!np) continue;
                // pool g = state rows t, t + 1 (t = t0 + 2 g). Its first row gets the set's pattern for "token" g, the
                // second a real-like row; a forced pool's second row scores -inf on every channel, so the pool is
                // exactly row t (weights exp(0) / 1 and 0 / 1), a midpoint vector: SkCompressPoolW's check fails
                std::vector<float> hv((size_t)(MMAX + 1) * HDIM), hs((size_t)(MMAX + 1) * HDIM);
                std::normal_distribution<float> sn(0.f, 2.f);
                unsigned nfc = 0;
                for (unsigned r = 0; r <= MMAX; ++r) {
                    const bool first = r >= t0 && (r - t0) % 2 == 0 && (r - t0) / 2 < np;
                    fill_norm(hv.data() + (size_t)r * HDIM, HDIM, first ? kind_of(set, (r - t0) / 2, np) : K_REAL, r);
                    for (unsigned i = 0; i < HDIM; ++i) hs[(size_t)r * HDIM + i] = sn(rng);
                }
                for (unsigned g2 = 0; g2 < np; ++g2) {
                    const size_t t = t0 + 2 * g2;
                    if (kind_of(set, g2, np) == K_FORCE)
                        for (unsigned i = 0; i < HDIM; ++i) hs[(t + 1) * HDIM + i] = -INFINITY;
                    nfc += kind_of(set, g2, np) == K_FORCE && forced(hv.data() + t * HDIM, HDIM);
                }
                forcedc += nfc;
                up(q, mkv, hv);
                up(q, msc, hs);
                {
                    sent(kna, (size_t)MMAX * HDIM * 4), sent(knb, (size_t)MMAX * HDIM * 4);
                    wgs<1024>(q, np, 32, CompressPoolPM<ActF32>{{2, (int)HDIM}, t0, np}, (const float *)mkv,
                              (const float *)msc, (const float *)wc, kna).wait();
                    wgs<1024>(q, np, 512, SkCompressPoolWM<ActF32>{{2, (int)HDIM}, t0, np}, (const float *)mkv,
                              (const float *)msc, (const float *)wc, knb).wait();
                    std::snprintf(ex, sizeof ex, " [%s; t0 %u, %u pools; forced kv rows %u]", set_name(set), t0, np, nfc);
                    report(same(down(q, knb, (size_t)MMAX * HDIM), down(q, kna, (size_t)MMAX * HDIM)),
                           "SkCompressPoolWM vs CompressPoolPM", m, ex);
                    ++nchk;
                }
            }
        }
        { // secondary: HcPostPrePMG vs HcPostPrePM (both engine call shapes: attention post, FFN post + pre copy)
            for (int shape = 0; shape < 2; ++shape) {
                const HcPostPrePM<ActF32> kp = shape ? HcPostPrePM<ActF32>{(int)H, m, H4, H, 4, 16, 4, 4, 4, H}
                                                     : HcPostPrePM<ActF32>{(int)H, m, H4, H, 4, 16, 0, 0, 4, H};
                const HcPostPrePMG<ActF32> kg{kp};
                const float *ps = shape ? hpre : nullptr;
                float *pda = shape ? hpd : nullptr;
                std::vector<float> rs, ro, rp;
                for (int f = 0; f < 2; ++f) {
                    q.memcpy(st2, st, (size_t)MMAX * H4 * 4).wait();
                    sent(f ? yb : ya, (size_t)MMAX * H * 4), sent(hpd, (size_t)MMAX * 4 * 4);
                    float *o = f ? yb : ya, *s2 = st2;
                    const float *xx = x, *po = hpost, *co = hcomb, *mi = hmix;
                    if (!f) q.parallel_for(sycl::nd_range<1>((size_t)m * H, 64), [=](sycl::nd_item<1> it) { kp(it, s2, xx, po, co, ps, shape ? pda : nullptr, mi, o); }).wait();
                    else q.parallel_for(sycl::nd_range<1>((size_t)m * H, 64), [=](sycl::nd_item<1> it) { kg(it, s2, xx, po, co, ps, shape ? pda : nullptr, mi, o); }).wait();
                    auto a1 = down(q, st2, (size_t)MMAX * H4), a2 = down(q, o, (size_t)MMAX * H), a3 = down(q, hpd, (size_t)MMAX * 4);
                    if (!f) rs = a1, ro = a2, rp = a3;
                    else report(same(a1, rs) && same(a2, ro) && same(a3, rp), shape ? "HcPostPrePMG vs HcPostPrePM (FFN shape)"
                                                                                     : "HcPostPrePMG vs HcPostPrePM (attention shape)", m);
                }
                ++nchk;
            }
        }
        if (6 * m <= 128) { // OWN_MT_EGSG: ExpertGroupSG vs ExpertGroupM (every written word; nothing else written)
            const unsigned nsl = 6 * m;
            unsigned neq = 0, nall = 0;
            for (int pat = 0; pat < 5; ++pat)
                for (int rep = 0; rep < 4; ++rep) {
                    up(q, egi, eg_ids(nsl, pat));
                    for (const unsigned cap : {1u, 2u, 6u, 8u, 16u})
                        for (const bool heavy : {false, true}) {
                            sent(ega, RUGrp::WORDS * 4), sent(egb, RUGrp::WORDS * 4);
                            eg_prod(q, nsl, cap, heavy, egi, ega).wait();
                            eg_sg(q, nsl, cap, heavy, egi, egb).wait();
                            const bool ok = same(down(q, ega, RUGrp::WORDS), down(q, egb, RUGrp::WORDS));
                            neq += ok, ++nall;
                            if (!ok) {
                                char ex[96];
                                std::snprintf(ex, sizeof ex, " [ids pattern %d, cap %u, heavy %d]", pat, cap, (int)heavy);
                                report(false, "ExpertGroupSG vs ExpertGroupM", m, ex);
                            }
                        }
                }
            nchk += nall;
            std::printf("m=%-3u ExpertGroupSG vs ExpertGroupM: %u of %u launches identical (%u slots)\n", m, neq, nall, nsl);
        }
        nforced_tot += forced5 + forcedp + forcedc;
        std::printf("m=%-3u bitwise sets done (%d sets; forced-chain tokens: 5120 %zu, pair %zu, pool rows %zu) %s\n", m,
                    NSET, forced5, forcedp, forcedc, g_fail ? "FAILURES SO FAR" : "all equal");
        std::fflush(stdout);
    }
    std::printf("bitwise: %zu comparisons, %d differ; %zu forced-chain vectors\n", nchk, g_fail, nforced_tot);
    if (notime) {
        std::printf("%s\n", g_fail ? "FAIL" : "PASS");
        return g_fail ? 1 : 0;
    }

    // ---------------------------------------------------------------- timing (real-like inputs; one all-forced row)
    { // clean timing inputs: real-like streams (no NaN / inf rows: those take SkDotsFF's fallback) and pool states
        std::vector<float> h((size_t)MMAX * H4), hv((size_t)(MMAX + 1) * HDIM), hs((size_t)(MMAX + 1) * HDIM);
        for (unsigned t = 0; t < MMAX; ++t)
            for (unsigned s = 0; s < 4; ++s) fill_norm(h.data() + t * H4 + s * H, H, K_REAL, t * 4 + s + 1000);
        std::normal_distribution<float> sn(0.f, 2.f);
        for (unsigned r = 0; r <= MMAX; ++r) fill_norm(hv.data() + (size_t)r * HDIM, HDIM, K_REAL, r + 2000);
        for (auto &v : hs) v = sn(rng);
        up(q, st, h), up(q, mkv, hv), up(q, msc, hs);
    }
    std::printf("\ntiming (us): cold / warm launch / warm chain; production -> new (order: %s first)\n",
                g_order ? "new" : "production");
    std::printf("%-4s %-34s %-26s %-26s\n", "m", "form", "production", "new");
    using F = std::function<std::pair<sycl::event, sycl::event>()>;
    auto row = [&](unsigned m, const char *name, const F &fp, const F &fnw) {
        spin(q, 20); // (~10 ms of reads: the card at its working clock, not idle-clocked after host work)
        Tm p{}, n{};
        if (g_order) n = timeit(q, fnw), p = timeit(q, fp);
        else p = timeit(q, fp), n = timeit(q, fnw);
        std::printf("%-4u %-34s %6.2f / %6.2f / %6.2f   %6.2f / %6.2f / %6.2f   (warm %+.2f)\n", m, name, p.cold, p.warm,
                    p.chain, n.cold, n.warm, n.chain, n.warm - p.warm);
        std::fflush(stdout);
    };
    spin(q, 300);
    for (const unsigned m : ms) {
        for (int set : {0, 4}) {
            if (set == 4 && m != 1 && m != 5 && m != 64) continue; // the forced (fallback) cost at a few sizes
            std::vector<float> hx, hq, hk;
            unsigned nf;
            fill_block(hx, H, m, set, nf);
            fill_block(hq, QR, m, set, nf);
            fill_block(hk, HDIM, m, set, nf);
            up(q, x, hx), up(q, qa, hq), up(q, kv, hk);
            const F n5p = [&] { return one(rows(q, T5{N5{x, w5, ya}, m, {H, H, 0, 0}})); };
            const F n5n = [&] { return one(wgl<32>(q, m, 512, SkNormWM<5120, 16>{m, H, H}, (const float *)x, (const float *)w5, yb)); };
            const F npp = [&] { return one(rows(q, TP{T1{N1{qa, wq, qna}, m, {QR, QR, 0, 0}}, T2{N2{kv, wk, kna}, m, {HDIM, HDIM, 0, 0}}})); };
            const F npn = [&] {
                return one(wgl<16>(q, m, 256, SkNormPairWM{m, QR, QR, HDIM, HDIM}, (const float *)qa, (const float *)wq, qnb,
                                   (const float *)kv, (const float *)wk, knb));
            };
            if (set) {
                row(m, "N5 (all forced)", n5p, n5n);
                row(m, "NP (all forced)", npp, npn);
                continue;
            }
            row(m, "N5", n5p, n5n);
            std::vector<unsigned> nts{m};
            if ((m + 5) / 6 != m) nts.push_back((m + 5) / 6); // all tokens' dots, and a sixth (a card's share)
            for (const unsigned nt : nts) {
                char nm[64];
                std::snprintf(nm, sizeof nm, "N5 + SkDotsWM<8> of %u tokens", nt);
                row(m, nm,
                    [&] {
                        auto a = rows(q, T5{N5{x, w5, ya}, m, {H, H, 0, 0}});
                        auto b = wgl<64>(q, (size_t)nt * 25, 512, SkDotsWM<8>{nt, H4, FS}, (const float *)st, (const float *)fn, da);
                        return std::make_pair(a, b);
                    },
                    [&] {
                        return one(wgl<64>(q, m + (size_t)nt * 25, 512, SkNormDotsWM<8>{m, nt, H, H, H4, FS}, (const float *)x,
                                           (const float *)w5, yb, (const float *)st, (const float *)fn, db));
                    });
            }
            {
                const unsigned nt = (m + 5) / 6;
                char nm[64];
                std::snprintf(nm, sizeof nm, "  SkDotsWM<8> of %u tokens alone", nt);
                const F d = [&] { return one(wgl<64>(q, (size_t)nt * 25, 512, SkDotsWM<8>{nt, H4, FS}, (const float *)st, (const float *)fn, da)); };
                row(m, nm, d, d);
            }
            row(m, "NP (q_a 1280 + kv 512)", npp, npn);
            row(m, "N512 (compressor ratio 1)", [&] { return one(rows(q, T2{N2{kv, wc, kna}, m, {HDIM, HDIM, 0, 0}})); },
                [&] { return one(wgl<4>(q, m, 64, SkNormWM<512, 2>{m, HDIM, HDIM}, (const float *)kv, (const float *)wc, knb)); });
            const unsigned np = (m + 1) / 2;
            char nm[64];
            std::snprintf(nm, sizeof nm, "CP (%u pools)", np);
            row(m, nm,
                [&] {
                    return one(wgs<1024>(q, np, 32, CompressPoolPM<ActF32>{{2, (int)HDIM}, 0u, np}, (const float *)mkv,
                                         (const float *)msc, (const float *)wc, kna));
                },
                [&] {
                    return one(wgs<1024>(q, np, 512, SkCompressPoolWM<ActF32>{{2, (int)HDIM}, 0u, np}, (const float *)mkv,
                                         (const float *)msc, (const float *)wc, knb));
                });
            // secondary: HcPostPrePM (the attention post + FFN pre-mix, 78 per check) with the item split by work-group
            const HcPostPrePM<ActF32> hk_{(int)H, m, H4, H, 4, 16, 0, 0, 4, H};
            row(m, "HcPostPrePM (index split by group)",
                [&] { return one(q.parallel_for(sycl::nd_range<1>((size_t)m * H, 64), [=](sycl::nd_item<1> it) {
                          hk_(it, st2, (const float *)x, (const float *)hpost, (const float *)hcomb, (const float *)nullptr,
                              (float *)nullptr, (const float *)hmix, ya);
                      })); },
                [&] { const HcPostPrePMG<ActF32> kg{hk_};
                      return one(q.parallel_for(sycl::nd_range<1>((size_t)m * H, 64), [=](sycl::nd_item<1> it) {
                          kg(it, st2, (const float *)x, (const float *)hpost, (const float *)hcomb, (const float *)nullptr,
                             (float *)nullptr, (const float *)hmix, yb);
                      })); });
            if (6 * m <= 128) {
                up(q, egi, eg_ids(6 * m, 0));
                char nm2[64];
                std::snprintf(nm2, sizeof nm2, "ExpertGroupM (%u slots, cap 6)", 6 * m);
                row(m, nm2, [&] { return one(eg_prod(q, 6 * m, 6, false, egi, ega)); },
                    [&] { return one(eg_sg(q, 6 * m, 6, false, egi, egb)); });
            }
        }
    }
    std::printf("%s\n", g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
