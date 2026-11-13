// bench_rep2m.cpp (rep2 helper, 2026-11-13): one card, the checks of 2-3 tokens: what the stream mixes' dot rows cost
// in the launches that carry them (engine forms: SkNormDotsWM<8> for the attention mix under qkv-1, FlNormKM<2,1,1> /
// RowsDotsK for the FFN mix), against the same launches without dot rows and with one card's rows (shares, bitwise).
// env: PL=layers (3)  NCOPY=8  REPS=40  ROUNDS=5  NSET=3  NOTIME=1
#include <sycl/sycl.hpp>
#include <fcntl.h>
#include <unistd.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <map>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41_rep2.hpp"
using namespace ops41sycl;
using Act = ActF32;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
static double median(std::vector<double> v) {
    if (v.empty()) return 0;
    std::sort(v.begin(), v.end());
    return v[v.size() / 2];
}
static int envi(const char *n, int d) { const char *e = getenv(n); return e ? atoi(e) : d; }
static std::vector<unsigned> env_list(const char *n, std::vector<unsigned> d) {
    const char *e = getenv(n);
    if (!e) return d;
    std::vector<unsigned> v;
    for (const char *p = e; *p;) {
        v.push_back((unsigned)strtoul(p, (char **)&p, 0));
        if (*p == ',') ++p;
    }
    return v;
}
#include "gguf_part.inc"


#include "stage2/packet3/kernels/sycl_v41_ck2.hpp"
static constexpr unsigned H = 5120, H4 = 4 * H, NC = 6, NE = 384, FS = 200;

// SkNormDotsWM<8> with the dot rows [d0, d0 + nr) of each of nd tokens: work-groups 0 .. m - 1 the norm (as
// SkNormDotsWM), work-group m + q runs SkDotsFF<8>::run for token q / nr's row d0 + q % nr (SkNormDotsWM's work-group
// m + 25 t + row's code). launch m + nd * nr work-groups.
struct SkNormDotsWMS {
    unsigned m, nd, d0, nr;
    size_t xs, ys, ss, os;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *x, const float *w, float *y, const float *streams,
                                     const float *fn, double *out, uint32_t *lm) const {
        const unsigned g = (unsigned)it.get_group_linear_id(), sgi = it.get_sub_group().get_group_linear_id();
        if (g < m) {
            SkNormSplit<5120, 16>::run(it, sgi, lm, 0, x + g * xs, w, y + g * ys);
            return;
        }
        const unsigned q = g - m, t = q / nr;
        if (t >= nd) return;
        SkDotsFF<8>::run(it, sgi, lm, d0 + q % nr, streams + t * ss, fn, out + t * os);
    }
};
// RowsDotsK<D> with the dot rows [d0, d0 + nr) of each of nd tokens
template <typename D> struct RowsDotsKS {
    D d;
    const float *streams, *fn;
    double *dout;
    size_t ss, os;
    unsigned nd, d0, nr;
    unsigned nrw() const { return (d.n() + 15) / 16; }
    size_t groups() const { return (size_t)nrw() + (size_t)nd * nr; }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, uint32_t *lm) const {
        const unsigned g = (unsigned)it.get_group_linear_id(), nrr = nrw();
        sycl::sub_group sg = it.get_sub_group();
        if (g < nrr) {
            const unsigned r = packed_row_id(it);
            if (r >= d.n()) return;
            d.row(sg, sg.get_local_linear_id(), r);
            return;
        }
        const unsigned q = g - nrr, t = q / nr;
        SkDotsFF<8>::run(it, sg.get_group_linear_id(), lm, d0 + q % nr, streams + t * ss, fn, dout + t * os);
    }
};

template <size_t SLM, typename K, typename... A> static sycl::event wgl(sycl::queue &q, size_t groups, size_t wg, K k, A... args) {
    return q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<uint32_t, 1> lt(SLM, hh);
        hh.parallel_for(sycl::nd_range<1>(groups * wg, wg), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            k(it, args..., &lt[0]);
        });
    });
}
template <typename K> static sycl::event ck2l(sycl::queue &q, const K &k) { // Backend41::ck2_launch
    return q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<uint32_t, 1> lm(K::lm_words(), hh);
        sycl::local_accessor<float, 1> xl(K::xl_floats(), hh);
        hh.parallel_for(sycl::nd_range<1>(k.groups() * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            k(it, &lm[0], xl.template get_multi_ptr<sycl::access::decorated::yes>());
        });
    });
}
template <typename K> static sycl::event rdk(sycl::queue &q, const K &k) { // Backend41::ck2_dots's launch
    return q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<uint32_t, 1> lm(64, hh);
        hh.parallel_for(sycl::nd_range<1>(k.groups() * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, &lm[0]); });
    });
}
static long g_cmp = 0;
static int g_fail = 0;
static std::vector<uint32_t> words(sycl::queue &q, const void *p, size_t n) {
    std::vector<uint32_t> v(n);
    q.memcpy(v.data(), p, n * 4).wait();
    return v;
}
static void check(const char *what, const std::vector<uint32_t> &a, const std::vector<uint32_t> &b, size_t lo, size_t hi) {
    size_t nd = 0, first = (size_t)-1;
    for (size_t i = lo; i < hi; ++i)
        if (a[i] != b[i]) { ++nd; if (first == (size_t)-1) first = i; }
    ++g_cmp;
    if (nd) { ++g_fail; std::printf("  DIFF %s: %zu of %zu words (first %zu)\n", what, nd, hi - lo, first); }
}
static void fill(sycl::queue &q, float *p, size_t n, std::mt19937 &g, float sd, float big) {
    std::normal_distribution<float> nd(0.f, sd);
    std::uniform_real_distribution<float> u(0.f, 1.f);
    std::vector<float> v(n);
    for (auto &f : v) { f = nd(g); if (u(g) < 0.002f) f *= big; }
    q.memcpy(p, v.data(), n * 4).wait();
}
using EvV = std::vector<sycl::event>;
struct Var {
    std::string name;
    std::function<void(int c, unsigned s, EvV &ev)> f;
    unsigned nshare;
};
static void time_vars(sycl::queue &q, std::vector<Var> &vars, int reps, int rounds, int ncopy, const char *tag, int L) {
    struct Key { size_t v; unsigned s; };
    std::vector<Key> keys;
    for (size_t v = 0; v < vars.size(); ++v)
        for (unsigned s = 0; s < vars[v].nshare; ++s) keys.push_back({v, s});
    std::vector<std::vector<double>> t(keys.size());
    { EvV ev; for (int r = 0; r < 400; ++r) vars[0].f(r % ncopy, 0, ev); q.wait(); }
    for (int warm = 0; warm < 2; ++warm)
        for (auto &k : keys) { EvV ev; for (int r = 0; r < 4; ++r) vars[k.v].f(r % ncopy, k.s, ev); q.wait(); }
    for (int rd = 0; rd < rounds; ++rd)
        for (size_t kk = 0; kk < keys.size(); ++kk) {
            const size_t k = rd % 2 ? keys.size() - 1 - kk : kk;
            EvV ev;
            for (int r = 0; r < reps; ++r) vars[keys[k].v].f((r + rd) % ncopy, keys[k].s, ev);
            q.wait();
            for (int r = 1; r < reps; ++r) t[k].push_back(ev_us(ev[(size_t)r]));
        }
    std::printf("timing %s layer %d (%d rounds x %d reps, %d copies, kernel us, median):\n", tag, L, rounds, reps - 1, ncopy);
    for (size_t v = 0; v < vars.size(); ++v) {
        std::vector<double> per;
        for (size_t k = 0; k < keys.size(); ++k)
            if (keys[k].v == v) per.push_back(median(t[k]));
        std::printf("  T %-3s L%-2d %-12s", tag, L, vars[v].name.c_str());
        if (per.size() == 1) std::printf(" %7.2f\n", per[0]);
        else {
            std::printf(" max %6.2f  shares:", *std::max_element(per.begin(), per.end()));
            for (double x : per) std::printf(" %6.2f", x);
            std::printf("\n");
        }
    }
}

int main() {
    const int ncopy = envi("NCOPY", 8), reps = envi("REPS", 40), rounds = envi("ROUNDS", 5), nset = envi("NSET", 3);
    const bool notime = envi("NOTIME", 0) != 0;
    sycl::queue q{sycl::gpu_selector_v, sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const auto dev = q.get_device();
    std::printf("device %s\n", dev.get_info<sycl::info::device::name>().c_str());
    if (!dev.has(sycl::aspect::ext_intel_free_memory)) { std::printf("free memory query unavailable\n"); return 3; }
    const size_t fm = dev.get_info<sycl::ext::intel::info::device::free_memory>();
    std::printf("free card memory %.2f GiB\n", fm / 1073741824.0);
    if (fm < ((size_t)2 << 30)) { std::printf("not enough free card memory\n"); return 3; }
    const std::vector<unsigned> layers = env_list("PL", {3});
    unsigned R0[NC], R1[NC];
    for (unsigned s = 0; s < NC; ++s) rep2_rows((int)NC, (int)s, R0[s], R1[s]);
    float *x = sycl::malloc_device<float>(8 * H, q), *y = sycl::malloc_device<float>(8 * H, q);
    float *streams = sycl::malloc_device<float>(8 * H4, q), *router = sycl::malloc_device<float>(8 * NE, q);
    double *d = sycl::malloc_device<double>(8 * FS, q);
    for (unsigned L : layers) {
        const std::string p = "blk." + std::to_string(L) + ".";
        const auto fa = f32_vec(p + "hc_attn_fn.weight", (size_t)24 * H4), ff = f32_vec(p + "hc_ffn_fn.weight", (size_t)24 * H4);
        const auto rt = packed_rows(p + "ffn_gate_inp.weight", iq3::Type::F32, H, 0, NE);
        std::vector<float *> FA, FF;
        std::vector<uint8_t *> RT;
        for (int c = 0; c < ncopy; ++c) FA.push_back(dcopy(q, fa)), FF.push_back(dcopy(q, ff)), RT.push_back(dcopy(q, rt));
        float *anw = dcopy(q, f32_vec(p + "attn_norm.weight", H)), *fnw = dcopy(q, f32_vec(p + "ffn_norm.weight", H));
        std::printf("\n== layer %u: checks of 2-3 tokens ==\n", L);
        for (unsigned M = 2; M <= 3; ++M) {
            // attention mix under qkv-1 (skdA): SkNormDotsWM<8>{M, M} = the engine's sknd; {M, 0} = the norm alone;
            // SkNormDotsWMS: card s's rows of every token
            auto KA = [&](int c, unsigned nd, EvV &ev) {
                ev.push_back(wgl<64>(q, M + (size_t)nd * 25, 512, SkNormDotsWM<8>{M, nd, H, H, H4, FS}, (const float *)x,
                                     (const float *)anw, y, (const float *)streams, (const float *)FA[c], d));
            };
            auto KAS = [&](int c, unsigned s, EvV &ev) {
                const unsigned nr = R1[s] - R0[s];
                ev.push_back(wgl<64>(q, M + (size_t)M * nr, 512, SkNormDotsWMS{M, M, R0[s], nr, H, H, H4, FS}, (const float *)x,
                                     (const float *)anw, y, (const float *)streams, (const float *)FA[c], d));
            };
            // FFN: M = 2 FlNormKM<2, 1, 1> (nt = 2 / 0); M = 3 RowsDotsK<DenseRowsG<GemvH16P<160>, 3>> (nd 3 / 0) + shares
            auto KF2 = [&](int c, unsigned nd, EvV &ev) {
                ev.push_back(ck2l(q, FlNormKM<2, 1, 1>{x, fnw, y, H, H, streams, FF[c], d, H4, FS, nd, RT[c], router, (size_t)NE, NE}));
            };
            using DR = DenseRowsG<GemvH16P<160, Act>, 3>;
            auto dr = [&](int c) { return DR{GemvH16P<160, Act>{NE}, RT[c], y, H, router, NE, 3u, 1u}; };
            auto KF3 = [&](int c, unsigned nd, EvV &ev) {
                ev.push_back(rdk(q, RowsDotsK<DR>{dr(c), streams, FF[c], d, H4, FS, nd}));
            };
            auto KF3S = [&](int c, unsigned s, EvV &ev) {
                ev.push_back(rdk(q, RowsDotsKS<DR>{dr(c), streams, FF[c], d, H4, FS, 3u, R0[s], R1[s] - R0[s]}));
            };
            // bitwise: shares' partials and norm outputs against the full launch
            std::mt19937 g(777u + L * 10 + M);
            for (int si = 0; si < nset; ++si) {
                fill(q, x, (size_t)M * H, g, si % 2 ? 1.0f : 0.5f, 30.f);
                fill(q, streams, (size_t)M * H4, g, si == nset - 1 ? 1.0f : 0.6f, 30.f);
                fill(q, y, (size_t)M * H, g, 1.0f, 3.f);
                q.memset(d, 0xff, (size_t)M * FS * 8).wait();
                { EvV ev; KA(0, M, ev); q.wait(); }
                const auto ad = words(q, d, (size_t)M * FS * 2), ay = words(q, y, (size_t)M * H);
                q.memset(d, 0xff, (size_t)M * FS * 8).wait();
                for (unsigned s = 0; s < NC; ++s) {
                    q.memset(y, 0xff, (size_t)M * H * 4).wait();
                    EvV ev;
                    KAS(0, s, ev);
                    q.wait();
                    check("KA share y", ay, words(q, y, (size_t)M * H), 0, (size_t)M * H);
                }
                check("KA shares d", ad, words(q, d, (size_t)M * FS * 2), 0, (size_t)M * FS * 2);
                if (M == 3) {
                    q.memset(d, 0xff, (size_t)M * FS * 8), q.memset(router, 0xff, (size_t)M * NE * 4), q.wait();
                    { EvV ev; KF3(0, 3, ev); q.wait(); }
                    const auto fd = words(q, d, (size_t)M * FS * 2), fr = words(q, router, (size_t)M * NE);
                    q.memset(d, 0xff, (size_t)M * FS * 8).wait();
                    for (unsigned s = 0; s < NC; ++s) {
                        q.memset(router, 0xff, (size_t)M * NE * 4).wait();
                        EvV ev;
                        KF3S(0, s, ev);
                        q.wait();
                        check("KF3 share router", fr, words(q, router, (size_t)M * NE), 0, (size_t)M * NE);
                    }
                    check("KF3 shares d", fd, words(q, d, (size_t)M * FS * 2), 0, (size_t)M * FS * 2);
                }
            }
            std::printf("bitwise M=%u: %ld comparisons so far, %d differ\n", M, g_cmp, g_fail);
            if (notime) continue;
            std::vector<Var> va = {{"A full", [&](int c, unsigned, EvV &ev) { KA(c, M, ev); }, 1},
                                   {"A share", KAS, NC},
                                   {"A norm only", [&](int c, unsigned, EvV &ev) { KA(c, 0, ev); }, 1}};
            time_vars(q, va, reps, rounds, ncopy, M == 2 ? "KA2" : "KA3", (int)L);
            std::vector<Var> vf;
            if (M == 2) vf = {{"F full", [&](int c, unsigned, EvV &ev) { KF2(c, 2, ev); }, 1},
                              {"F no dots", [&](int c, unsigned, EvV &ev) { KF2(c, 0, ev); }, 1}};
            else vf = {{"F full", [&](int c, unsigned, EvV &ev) { KF3(c, 3, ev); }, 1},
                       {"F share", KF3S, NC},
                       {"F no dots", [&](int c, unsigned, EvV &ev) { KF3(c, 0, ev); }, 1}};
            time_vars(q, vf, reps, rounds, ncopy, M == 2 ? "KF2" : "KF3", (int)L);
        }
        for (int c = 0; c < ncopy; ++c) sycl::free(FA[c], q), sycl::free(FF[c], q), sycl::free(RT[c], q);
        sycl::free(anw, q), sycl::free(fnw, q);
    }
    std::printf("\nALL: %ld comparisons, %d differ: %s\n", g_cmp, g_fail, g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
