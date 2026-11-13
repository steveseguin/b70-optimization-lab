// bench_rep2r.cpp (rep2 helper, 2026-11-13; head copied from bench_rep2m.cpp): one card, checks of 4-6 tokens: the
// router rows' launch (dense_m's RowsP<DenseRowsG<GemvH16P<160>, G>> with OWN_MT_TGM's G: 4 -> 2, 5 -> 3, 6 -> 3,
// launch_rows<0>) for all 384 rows against one card's 64 rows [64 s, 64 s + 64) (option (a)'s share; bitwise).
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

template <typename K> static sycl::event rows0(sycl::queue &q, size_t rows, K k) { // launch_rows<0>: 16 rows per 512
    const size_t nwg = (rows + 15) / 16;
    return q.submit([&](sycl::handler &hh) {
        hh.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it); });
    });
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
    float *y = sycl::malloc_device<float>(16 * H, q), *router = sycl::malloc_device<float>(16 * NE, q);
    for (unsigned L : layers) {
        const std::string p = "blk." + std::to_string(L) + ".";
        const auto rt = packed_rows(p + "ffn_gate_inp.weight", iq3::Type::F32, H, 0, NE);
        const size_t rtb = rt.size() / NE;
        std::vector<uint8_t *> RT;
        for (int c = 0; c < ncopy; ++c) RT.push_back(dcopy(q, rt));
        std::printf("\n== layer %u: router rows at checks of 4-6 tokens (row bytes %zu) ==\n", L, rtb);
        for (unsigned M = 4; M <= 6; ++M) {
            auto run = [&](auto gc, int c, unsigned e0, unsigned n, EvV &ev) {
                constexpr unsigned G = decltype(gc)::value;
                using DR = DenseRowsG<GemvH16P<160, Act>, G>;
                const DR d{GemvH16P<160, Act>{n}, RT[c] + (size_t)e0 * rtb, y, H, router + e0, NE, M, (M + G - 1) / G};
                ev.push_back(rows0(q, d.n(), RowsP<DR>{d}));
            };
            auto go = [&](int c, unsigned e0, unsigned n, EvV &ev) {
                if (M == 4) run(std::integral_constant<unsigned, 2>{}, c, e0, n, ev);
                else run(std::integral_constant<unsigned, 3>{}, c, e0, n, ev);
            };
            std::mt19937 g(4242u + L * 10 + M);
            for (int si = 0; si < nset; ++si) {
                fill(q, y, (size_t)M * H, g, si % 2 ? 1.0f : 0.5f, 30.f);
                q.memset(router, 0xff, (size_t)M * NE * 4).wait();
                { EvV ev; go(0, 0, NE, ev); q.wait(); }
                const auto fr = words(q, router, (size_t)M * NE);
                q.memset(router, 0xff, (size_t)M * NE * 4).wait();
                for (unsigned s = 0; s < NC; ++s) { EvV ev; go(0, NE * s / NC, NE / NC, ev); q.wait(); }
                check("R shares router", fr, words(q, router, (size_t)M * NE), 0, (size_t)M * NE);
            }
            std::printf("bitwise M=%u: %ld comparisons so far, %d differ\n", M, g_cmp, g_fail);
            if (notime) continue;
            std::vector<Var> v = {{"R full", [&](int c, unsigned, EvV &ev) { go(c, 0, NE, ev); }, 1},
                                  {"R share", [&](int c, unsigned s, EvV &ev) { go(c, NE * s / NC, NE / NC, ev); }, NC}};
            const std::string tag = "R" + std::to_string(M);
            time_vars(q, v, reps, rounds, ncopy, tag.c_str(), (int)L);
        }
        for (int c = 0; c < ncopy; ++c) sycl::free(RT[c], q);
    }
    std::printf("\nALL: %ld comparisons, %d differ: %s\n", g_cmp, g_fail, g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
