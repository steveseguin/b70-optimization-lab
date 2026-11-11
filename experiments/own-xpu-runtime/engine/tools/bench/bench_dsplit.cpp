// pcd-1 (prefill plan item C, 2026-11-11), one card: the stream mixes' dot rows in prompt blocks.
// Bitwise (every M of MS):
//  (1) OWN_MT_DSPLIT: the cards' token shares of HcDotsRows's rows (tpm_layer's dmix: the streams and partials
//      pointers moved to the share's first token, m = the share), launched one after another into one region, give
//      exactly the full launch's partials (memcmp over all M tokens; nothing written past them); the finish of all M
//      tokens (HcFinishRows, form 1 = OWN_HC_FIN=1 and form 0) from the region equals the production finish.
//      Splits: the attention default (12,12,12,12,8,8 heads -> weights 1,1,1,1,4,4), the FFN default (1 each), and
//      OWN_MT_DSPLIT_WA=0,0,0,0,1,1.
//  (2) OWN_MT_SKDOTS: SkDotsWM<8> / <4>'s partials (all M tokens, and the attention split's shares into one region:
//      the same partials as the full launch), finished, give the production finish's pre / post / comb bit for bit
//      (the partials themselves differ: T and zeros, or the production partials where SkDotsFF's check fails; the
//      count of such rows is printed).
// Timing (cold: 256 MiB read before every launch; median of REPS): the dot rows alone for n tokens (512-item
// work-groups, as rows_launch past OWN_MT_RWG=128 rows), SkDotsWM<8> for n tokens, Q8_0 q_a (1280 x 5120,
// DenseRowsG<GemvQ8P<160>, 4>: the engine's form for blocks of 16+ tokens at OWN_MT_TG=4) alone, with every token's
// dot rows (production OWN_MT_RIDE=1) and with the shares of a 12-head card / an 8-head card (attention split) and
// of the FFN split's largest share, and the finish rows of M tokens as their own launch (rows_launch's forms).
//   env MS=16,64,256 REPS=21 NOTIME=1 (bitwise only) SEED=1
// build (engine dir with pcd-1 applied; a patched copy: -I <copy>/src first):
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src -I tools/bench tools/bench/bench_dsplit.cpp -o $S/bench_dsplit
// run: ONEAPI_DEVICE_SELECTOR=level_zero:<N> $S/bench_dsplit     Exit status 1 on any mismatch.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
using namespace ops41sycl;

static constexpr unsigned MMAX = 264, H = 5120, FS = 25 * 8; // tokens in the buffers (MTA), width, partials/token
static constexpr size_t H4 = 4 * (size_t)H;
static constexpr size_t FLUSH_WORDS = (size_t)64 << 20; // 256 MiB
static uint32_t *g_flush = nullptr;
static int g_fail = 0, g_reps = 21;
static bool g_notime = false;
using HD = TokRows<HcDotsRows<5120, 8>>;
using FR = TokRows<HcFinishRows>;

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
template <typename T> static T *dev_copy(sycl::queue &q, const std::vector<T> &h) {
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
static std::vector<uint8_t> packed_q8(unsigned cols, unsigned rows, unsigned seed) { // bench_dense_ws's packed_rand
    const iq3::Type t = iq3::Type::Q8_0;
    const auto L = iq3::layout(t);
    const size_t rb = (size_t)cols / L.elements * L.bytes, prb = pk41::packed_row_bytes(t, cols);
    std::mt19937 rng(seed);
    std::vector<uint8_t> hw((size_t)rows * rb);
    for (auto &b : hw) b = uint8_t(rng());
    for (size_t blk = 0; blk < hw.size() / L.bytes; ++blk) {
        const uint16_t h = 0x1400 + (rng() & 0x3ff);
        hw[blk * L.bytes] = h & 255;
        hw[blk * L.bytes + 1] = h >> 8;
    }
    std::vector<uint8_t> hp((size_t)rows * prb);
    for (size_t r = 0; r < rows; ++r) pk41::pack_row(t, hw.data() + r * rb, hp.data() + r * prb, cols);
    return hp;
}
// rows_launch's forms: one sub-group per work-group up to 128 rows (OWN_MT_RWG=128), else 512 items
template <typename RW> static sycl::event rows(sycl::queue &q, const RW &rw) {
    const RowsP<RW> kr{rw};
    const size_t n = rw.n(), wg = n <= 128 ? 32 : 512, per = wg / 32, nwg = std::max<size_t>(1, (n + per - 1) / per);
    return q.parallel_for(sycl::nd_range<1>(nwg * wg, wg), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kr(it); });
}
template <unsigned K> static sycl::event sk(sycl::queue &q, unsigned nt, const float *sv, const float *fn, double *out) {
    const SkDotsWM<K> k{nt, H4, FS};
    return q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<uint32_t, 1> lt(64, hh);
        hh.parallel_for(sycl::nd_range<1>((size_t)nt * 25 * 512, 512),
                        [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, sv, fn, out, &lt[0]); });
    });
}
template <typename F> static double med(sycl::queue &q, F &&f) {
    for (int i = 0; i < 3; ++i) f();
    q.wait();
    std::vector<double> t;
    for (int r = 0; r < g_reps; ++r) {
        flush(q, (uint32_t)r);
        sycl::event e = f();
        q.wait();
        t.push_back(ev_us(e));
    }
    std::sort(t.begin(), t.end());
    return t[t.size() / 2];
}
// ds_split (backend_sycl_v41_mt.inc) for six cards and weights w
static void split(unsigned M, const long *w, unsigned *t0, unsigned *t1) {
    long W = 0, cw = 0;
    for (int d = 0; d < 6; ++d) W += w[d];
    unsigned prev = 0;
    for (int d = 0; d < 6; ++d) {
        cw += w[d];
        const unsigned e = d == 5 ? M : (unsigned)std::min<long>(M, ((long)M * cw + W / 2) / W);
        t0[d] = prev;
        t1[d] = prev = std::max(prev, e);
    }
}
static HD dots_of(const float *streams, const float *fn, double *out, unsigned t0, unsigned t1) {
    return HD{HcDotsRows<5120, 8>{streams + t0 * H4, fn, out + (size_t)t0 * FS}, t1 - t0, {H4, FS, 0, 0}};
}
struct Fin { // a finish's outputs (pre 4, post 4, comb 16 floats per token)
    float *pre, *post, *comb;
};
static std::vector<float> fin_run(sycl::queue &q, const Fin &o, const double *d, const float *scale, const float *base,
                                  unsigned M, int form) {
    q.memset(o.pre, 0xff, MMAX * 24 * 4).wait(); // (pre, post, comb are one allocation)
    HcMixFinishSG k{(int)H, 8};
    k.form = form;
    rows(q, FR{HcFinishRows{k, d, scale, base, o.pre, o.post, o.comb}, M, {FS, 4, 4, 16}}).wait();
    std::vector<float> h(MMAX * 24);
    q.memcpy(h.data(), o.pre, h.size() * 4).wait();
    return h;
}
static std::vector<double> get_d(sycl::queue &q, const double *d) {
    std::vector<double> h((size_t)MMAX * FS);
    q.memcpy(h.data(), d, h.size() * 8).wait();
    return h;
}
template <typename T> static bool bits_eq(const std::vector<T> &a, const std::vector<T> &b, size_t n = ~(size_t)0) {
    n = std::min({n, a.size(), b.size()});
    return a.size() == b.size() && !std::memcmp(a.data(), b.data(), n * sizeof(T)); // (bit patterns: NaN fill too)
}
static void report(bool ok, const char *what, unsigned M, const char *extra = "") {
    std::printf("%s M=%-3u %s%s\n", ok ? "bitwise" : "DIFFERS", M, what, extra);
    std::fflush(stdout);
    g_fail += !ok;
}

int main() {
    std::vector<unsigned> ms{16, 64, 256};
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
    g_notime = getenv("NOTIME") && atoi(getenv("NOTIME")) != 0;
    const unsigned seed = getenv("SEED") ? (unsigned)atoi(getenv("SEED")) : 1u;
    sycl::queue q{sycl::gpu_selector_v, sycl::property_list{sycl::property::queue::in_order{},
                                                            sycl::property::queue::enable_profiling{}}};
    std::printf("device: %s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    g_flush = sycl::malloc_device<uint32_t>(FLUSH_WORDS, q);
    q.memset(g_flush, 0, FLUSH_WORDS * 4).wait();
    const float *streams = dev_copy(q, rand_f((size_t)MMAX * H4, seed + 10, -1.0f, 1.0f));
    const float *fn = dev_copy(q, rand_f((size_t)24 * H4, seed + 11, -0.05f, 0.05f));
    const float *scale = dev_copy(q, std::vector<float>{0.5f, 0.7f, 0.9f});
    const float *base = dev_copy(q, rand_f(24, seed + 12, -0.5f, 0.5f));
    double *dref = sycl::malloc_device<double>((size_t)MMAX * FS, q), *dreg = sycl::malloc_device<double>((size_t)MMAX * FS, q);
    float *fo = sycl::malloc_device<float>((size_t)MMAX * 24, q);
    const Fin fin{fo, fo + MMAX * 4, fo + MMAX * 8};
    const long WA[6] = {1, 1, 1, 1, 4, 4}, WF[6] = {1, 1, 1, 1, 1, 1}, W45[6] = {0, 0, 0, 0, 1, 1};
    const struct { const char *name; const long *w; } splits[] = {{"attention", WA}, {"ffn", WF}, {"WA=0,0,0,0,1,1", W45}};
    // ---- bitwise
    for (const unsigned M : ms) {
        if (M < 1 || M > MMAX - 8) { std::printf("M=%u: outside 1..%u\n", M, MMAX - 8); return 2; }
        q.memset(dref, 0xff, (size_t)MMAX * FS * 8).wait();
        rows(q, dots_of(streams, fn, dref, 0, M)).wait();
        const auto ref = get_d(q, dref);
        const auto fref1 = fin_run(q, fin, dref, scale, base, M, 1), fref0 = fin_run(q, fin, dref, scale, base, M, 0);
        for (const auto &sp : splits) {
            unsigned t0[6], t1[6];
            split(M, sp.w, t0, t1);
            q.memset(dreg, 0xff, (size_t)MMAX * FS * 8).wait();
            for (int d = 0; d < 6; ++d)
                if (t1[d] > t0[d]) rows(q, dots_of(streams, fn, dreg, t0[d], t1[d]));
            q.wait();
            const auto got = get_d(q, dreg);
            size_t stray = 0;
            for (size_t i = (size_t)M * FS; i < got.size(); ++i) {
                uint64_t u;
                std::memcpy(&u, &got[i], 8);
                stray += u != ~0ull;
            }
            char ex[96];
            std::snprintf(ex, sizeof ex, " (tokens %u,%u,%u,%u,%u,%u; %zu stray)", t1[0] - t0[0], t1[1] - t0[1],
                          t1[2] - t0[2], t1[3] - t0[3], t1[4] - t0[4], t1[5] - t0[5], stray);
            const bool same = !std::memcmp(got.data(), ref.data(), (size_t)M * FS * 8) && !stray;
            std::string w = std::string("dsplit partials, ") + sp.name + " split";
            report(same, w.c_str(), M, ex);
            const bool f1 = bits_eq(fin_run(q, fin, dreg, scale, base, M, 1), fref1),
                       f0 = bits_eq(fin_run(q, fin, dreg, scale, base, M, 0), fref0);
            w = std::string("dsplit finish (forms 1, 0), ") + sp.name + " split";
            report(f1 && f0, w.c_str(), M);
        }
        auto skcheck = [&](auto kc) {
            constexpr unsigned K = decltype(kc)::value;
            q.memset(dreg, 0xff, (size_t)MMAX * FS * 8).wait();
            sk<K>(q, M, streams, fn, dreg).wait();
            const auto got = get_d(q, dreg);
            size_t fb = 0;
            for (unsigned t = 0; t < M; ++t)
                for (unsigned r = 0; r < 25; ++r) {
                    bool z = true;
                    for (unsigned k = 1; k < 8; ++k) z &= got[(size_t)t * FS + 8 * r + k] == 0.0;
                    fb += !z;
                }
            char ex[64];
            std::snprintf(ex, sizeof ex, " (%zu of %u rows took the production fallback)", fb, M * 25);
            const bool f1 = bits_eq(fin_run(q, fin, dreg, scale, base, M, 1), fref1),
                       f0 = bits_eq(fin_run(q, fin, dreg, scale, base, M, 0), fref0);
            std::string w = "skdots<" + std::to_string(K) + "> finish (forms 1, 0) vs production";
            report(f1 && f0, w.c_str(), M, ex);
            unsigned t0[6], t1[6]; // the attention split's shares into one region: the full launch's partials
            split(M, WA, t0, t1);
            double *dsh = dref; // (dref's reference copy is on the host)
            q.memset(dsh, 0xff, (size_t)MMAX * FS * 8).wait();
            for (int d = 0; d < 6; ++d)
                if (t1[d] > t0[d]) sk<K>(q, t1[d] - t0[d], streams + t0[d] * H4, fn, dsh + (size_t)t0[d] * FS);
            q.wait();
            const auto sh = get_d(q, dsh);
            w = "skdots<" + std::to_string(K) + "> shares = full launch";
            report(bits_eq(sh, got, (size_t)M * FS), w.c_str(), M);
            q.memcpy(dref, ref.data(), ref.size() * 8).wait();
        };
        skcheck(std::integral_constant<unsigned, 8>{});
        skcheck(std::integral_constant<unsigned, 4>{});
    }
    if (g_notime) return g_fail ? 1 : 0;
    // ---- timing
    const auto hw = packed_q8(5120, 1280, seed + 20);
    const uint8_t *w = dev_copy(q, hw);
    const float *x = dev_copy(q, rand_f((size_t)MMAX * 5120, seed + 21, -2.0f, 2.0f));
    float *y = sycl::malloc_device<float>((size_t)MMAX * 1280, q);
    using QA = DenseRowsG<GemvQ8P<160, ActF32>, 4>;
    for (const unsigned M : ms) {
        unsigned a0[6], a1[6], f0[6], f1[6];
        split(M, WA, a0, a1);
        split(M, WF, f0, f1);
        unsigned fmax = 0;
        for (int d = 0; d < 6; ++d) fmax = std::max(fmax, f1[d] - f0[d]);
        const unsigned n12 = a1[0] - a0[0], n8 = a1[4] - a0[4];
        const QA qa{GemvQ8P<160, ActF32>{1280, 0}, w, x, 5120, y, 1280, M, (M + 3) / 4};
        std::printf("-- M=%u (attention shares: %u tokens on a 12-head card, %u on an 8-head card; ffn share <= %u)\n", M,
                    n12, n8, fmax);
        for (const unsigned n : {M, n12, n8, fmax}) {
            if (!n) continue;
            const double hd = med(q, [&] { return rows(q, dots_of(streams, fn, dref, 0, n)); });
            const double s8 = med(q, [&] { return sk<8>(q, n, streams, fn, dref); });
            std::printf("   dot rows of %3u tokens: HcDotsRows alone %8.1f us   SkDotsWM<8> %7.1f us\n", n, hd, s8);
        }
        const double qa0 = med(q, [&] { return rows(q, qa); });
        auto with = [&](unsigned n) {
            return med(q, [&] { return rows(q, RowsPair<HD, QA>{dots_of(streams, fn, dref, 0, n), qa}); });
        };
        const double qm = with(M), q12 = with(n12), q8 = with(n8), qf = with(fmax);
        std::printf("   q_a Q8_0 1280x5120 G4: alone %7.1f us | + dots of %u tokens %7.1f | + %u %7.1f | + %u %7.1f | + %u %7.1f\n",
                    qa0, M, qm, n12, q12, n8, q8, fmax, qf);
        HcMixFinishSG k{(int)H, 8};
        k.form = 1;
        const FR fr{HcFinishRows{k, dref, scale, base, fin.pre, fin.post, fin.comb}, M, {FS, 4, 4, 16}};
        std::printf("   finish rows of %u tokens, own launch: %6.1f us\n", M, med(q, [&] { return rows(q, fr); }));
        std::fflush(stdout);
    }
    std::printf("%s\n", g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
