// bench_dots.cpp (rep2 helper, 2026-11-13; dots/README.md): one card. The one-token norm + dot-row launches and their
// parts, cold (weight copies cycled over > 3x the card's cache) and hot (one copy):
//   E1 / E26 / E49   empty launches of 1 / 26 / 49 work-groups of 512 (launch floor)
//   N                SkNormW<5120, 16> (the norm alone, one work-group)
//   D1 / D25         SkDotsFF<8> rows: one work-group (row 0) / 25 work-groups (the attention mix's rows)
//   A                SkNormDotsW<8> (production attention launch)
//   R                GemvH16P<160> router rows alone over a ready normalized vector (24 work-groups, launch_rows)
//   RN               FlNormK with no dot rows (router + every work-group's norm prologue)
//   F                FlNormK<5120,16,25,8,0,NoRows,FlH16Rows<160>> (production FFN launch)
//   R8 / R4 / R1     the router rows at 8 / 4 / 1 rows per work-group of 8 / 4 / 1 sub-groups (row body unchanged)
//   DPsxn            SkDotsFF<8>'s 16 sub-group chains of n rows on work-groups of s sub-groups (16 / s per row), no
//                    combine / check (how fast one row's bytes arrive when spread over more Xe cores)
//   AP<h> / RNP<h> / FP<h> / FPD<h>   the prefetch forms (sycl_v41_dots.hpp), h = 1 (L1 hint) / 3 (L3 hint)
// Bitwise: every form's outputs (y, the 200 partial words, the 384 logits) against production's, every copy state.
// env: PL=layers (0)  REPS=40  ROUNDS=5  NSET=3  NOTIME=1  ONLY=substring of the variant names to time
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
#include "stage2/packet3/kernels/sycl_v41_fl.hpp"
#include "stage2/packet3/kernels/sycl_v41_dots.hpp"
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

static constexpr unsigned H = 5120, H4 = 4 * H, NE = 384;
using EvV = std::vector<sycl::event>;
struct EmptyK {
    void operator()(sycl::nd_item<1>) const {}
};
struct DotsK { // SkDotsFF<8> rows r0 + g
    unsigned r0;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *streams, const float *fn, double *out, uint32_t *lm) const {
        SkDotsFF<8>::run(it, it.get_sub_group().get_group_linear_id(), lm, r0 + (unsigned)it.get_group_linear_id(), streams, fn, out);
    }
};
template <int HINT> struct DotsKP {
    unsigned r0;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *streams, const float *fn, double *out, uint32_t *lm) const {
        SkDotsPF<8, HINT>::run(it, it.get_sub_group().get_group_linear_id(), lm, r0 + (unsigned)it.get_group_linear_id(), streams, fn, out);
    }
};
// ledger only (timing; R* logits also compared): GemvH16P<160>'s row body with RPW rows per work-group of RPW sub-groups
template <unsigned RPW> struct RouterRowsK {
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, float *y, uint32_t *) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned r = (unsigned)it.get_group_linear_id() * RPW + sg.get_group_linear_id();
        if (r >= NE) return;
        GemvH16P<160, Act>{NE}.row(sg, sg.get_local_linear_id(), r, w, x, y);
    }
};
// ledger only (timing): SkDotsFF<8>'s 16 per-sub-group chains of a row (loop + lane tree copied) on work-groups of SPW
// sub-groups (16 / SPW work-groups per row), each sub-group's (acc, ef) stored; no combine, no check
template <unsigned SPW> struct DotsPartK {
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *streams, const float *fn, double *part, uint32_t *) const {
        using F = SkDotsFF<8>;
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), gi = (unsigned)it.get_group_linear_id();
        const unsigned r = gi / (16 / SPW), sgi = (gi % (16 / SPW)) * SPW + sg.get_group_linear_id();
        const float *fr = fn + (size_t)(r < 24 ? r : 0) * F::N;
        double acc = 0;
        float ef = 0;
#pragma unroll
        for (unsigned k = 0; k < F::MY; ++k) {
            const unsigned g = sgi + k * F::SGS;
            if (g < F::NCH) {
                const auto a = sg_bloadN<8>(sg, streams + g * 256);
                const auto b = r < 24 ? sg_bloadN<8>(sg, fr + g * 256) : a;
                float hi = 0, lo = 0;
#pragma unroll
                for (unsigned m = 0; m < 8; ++m) {
                    const float p = b[m] * a[m];
                    const float e = sycl::fma(b[m], a[m], -p);
                    const float t = hi + p;
                    const float z = t - hi;
                    const float er = (hi - (t - z)) + (p - z);
                    hi = t;
                    lo = lo + (er + e);
                    ef = ef + sycl::fabs(p);
                }
                acc = acc + double(hi);
                acc = acc + double(lo);
            }
        }
        for (int w = 16; w; w >>= 1) {
            acc += sycl::select_from_group(sg, acc, (int)lane ^ w);
            ef += sycl::select_from_group(sg, ef, (int)lane ^ w);
        }
        if (lane == 0) part[2 * (r * 16 + sgi)] = acc, part[2 * (r * 16 + sgi) + 1] = ef;
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
template <typename K> static sycl::event flk(sycl::queue &q, const K &k, size_t xsn) { // Backend41::fl_norm_launch
    const size_t ng = k.groups();
    return q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<uint32_t, 1> lm(64, hh);
        sycl::local_accessor<float, 1> xs(xsn ? xsn : 1, hh);
        hh.parallel_for(sycl::nd_range<1>(ng * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            k(it, &lm[0], xs.template get_multi_ptr<sycl::access::decorated::yes>());
        });
    });
}
static sycl::event empty(sycl::queue &q, size_t groups) {
    return q.submit([&](sycl::handler &hh) {
        hh.parallel_for(sycl::nd_range<1>(groups * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { EmptyK{}(it); });
    });
}
template <typename K, typename... A> static sycl::event rows0(sycl::queue &q, size_t rows, K k, A... args) { // launch_rows<0>
    const size_t nwg = (rows + 15) / 16;
    return q.submit([&](sycl::handler &hh) {
        hh.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, args...); });
    });
}

static long g_cmp = 0;
static int g_fail = 0;
static std::vector<uint32_t> words(sycl::queue &q, const void *p, size_t n) {
    std::vector<uint32_t> v(n);
    q.memcpy(v.data(), p, n * 4).wait();
    return v;
}
static void check(const std::string &what, const std::vector<uint32_t> &a, const std::vector<uint32_t> &b) {
    size_t nd = 0, first = (size_t)-1;
    for (size_t i = 0; i < a.size(); ++i)
        if (a[i] != b[i]) { ++nd; if (first == (size_t)-1) first = i; }
    ++g_cmp;
    if (nd) { ++g_fail; std::printf("  DIFF %s: %zu of %zu words (first %zu)\n", what.c_str(), nd, a.size(), first); }
}
static void fill(sycl::queue &q, float *p, size_t n, std::mt19937 &g, float sd, float big) {
    std::normal_distribution<float> nd(0.f, sd);
    std::uniform_real_distribution<float> u(0.f, 1.f);
    std::vector<float> v(n);
    for (auto &f : v) { f = nd(g); if (u(g) < 0.002f) f *= big; }
    q.memcpy(p, v.data(), n * 4).wait();
}

struct Var {
    std::string name;
    std::function<void(int c, EvV &ev)> f;
    int ncopy; // copies cycled (1: hot)
};
static void time_vars(sycl::queue &q, std::vector<Var> &vars, int reps, int rounds, int L) {
    std::vector<std::vector<double>> t(vars.size());
    { EvV ev; for (int r = 0; r < 400; ++r) vars[0].f(r % vars[0].ncopy, ev); q.wait(); }
    for (int rd = 0; rd < rounds; ++rd)
        for (size_t kk = 0; kk < vars.size(); ++kk) {
            const size_t k = rd % 2 ? vars.size() - 1 - kk : kk;
            EvV ev;
            for (int r = 0; r < reps; ++r) vars[k].f((r + rd * 7) % vars[k].ncopy, ev);
            q.wait();
            for (int r = 1; r < reps; ++r) t[k].push_back(ev_us(ev[(size_t)r]));
        }
    std::printf("timing layer %d (%d rounds x %d reps, kernel us: median [p10 p90]):\n", L, rounds, reps - 1);
    for (size_t v = 0; v < vars.size(); ++v) {
        auto s = t[v];
        std::sort(s.begin(), s.end());
        std::printf("  T L%-2d %-10s %-4s %7.2f  [%6.2f %6.2f]\n", L, vars[v].name.c_str(), vars[v].ncopy > 1 ? "cold" : "hot",
                    median(t[v]), s[s.size() / 10], s[s.size() * 9 / 10]);
    }
}

int main() {
    const int reps = envi("REPS", 40), rounds = envi("ROUNDS", 5), nset = envi("NSET", 3);
    const bool notime = getenv("NOTIME") != nullptr;
    const char *only = getenv("ONLY");
    sycl::queue q{sycl::gpu_selector_v, sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const auto dev = q.get_device();
    const size_t l2 = dev.get_info<sycl::info::device::global_mem_cache_size>();
    std::printf("device %s, %u compute units, cache %.1f MiB, %u max work-group\n", dev.get_info<sycl::info::device::name>().c_str(),
                dev.get_info<sycl::info::device::max_compute_units>(), l2 / 1048576.0,
                (unsigned)dev.get_info<sycl::info::device::max_work_group_size>());
    if (!dev.has(sycl::aspect::ext_intel_free_memory)) { std::printf("free memory query unavailable\n"); return 3; }
    const size_t fm = dev.get_info<sycl::ext::intel::info::device::free_memory>();
    std::printf("free card memory %.2f GiB\n", fm / 1073741824.0);
    if (fm < ((size_t)4 << 30)) { std::printf("not enough free card memory\n"); return 3; }
    float *x = sycl::malloc_device<float>(H, q), *nwA = nullptr, *nwF = nullptr, *y = sycl::malloc_device<float>(H, q);
    float *yr = sycl::malloc_device<float>(H, q); // the router's ready input (R)
    float *streams = sycl::malloc_device<float>(H4, q), *router = sycl::malloc_device<float>(NE, q);
    double *d = sycl::malloc_device<double>(200, q);
    double *part = sycl::malloc_device<double>(2 * 25 * 16, q);
    for (unsigned L : env_list("PL", {0})) {
        const std::string p = "blk." + std::to_string(L) + ".";
        const auto fa = f32_vec(p + "hc_attn_fn.weight", (size_t)24 * H4), ff = f32_vec(p + "hc_ffn_fn.weight", (size_t)24 * H4);
        const auto rt = packed_rows(p + "ffn_gate_inp.weight", iq3::Type::F32, H, 0, NE);
        const int cf = (int)((3 * l2) / (fa.size() * 4) + 1), cr = (int)((3 * l2) / rt.size() + 1);
        std::vector<float *> FA, FF;
        std::vector<uint8_t *> RT;
        for (int c = 0; c < cf; ++c) FA.push_back(dcopy(q, fa)), FF.push_back(dcopy(q, ff));
        for (int c = 0; c < cr; ++c) RT.push_back(dcopy(q, rt));
        nwA = dcopy(q, f32_vec(p + "attn_norm.weight", H)), nwF = dcopy(q, f32_vec(p + "ffn_norm.weight", H));
        std::printf("\n== layer %u: fn rows %zu B x %d copies, router %zu B x %d copies ==\n", L, fa.size() * 4, cf, rt.size(), cr);
        const int ccold = std::max(cf, cr);
        // the launches (c: copy index; fn copies and router copies taken modulo their counts)
        using FR = FlH16Rows<160>;
        auto A = [&](int c, EvV &ev) { ev.push_back(wgl<64>(q, 26, 512, SkNormDotsW<8>{}, (const float *)x, (const float *)nwA, y, (const float *)streams, (const float *)FA[c % cf], d)); };
        auto AP1 = [&](int c, EvV &ev) { ev.push_back(wgl<64>(q, 26, 512, SkNormDotsWP<8, 1>{}, (const float *)x, (const float *)nwA, y, (const float *)streams, (const float *)FA[c % cf], d)); };
        auto AP3 = [&](int c, EvV &ev) { ev.push_back(wgl<64>(q, 26, 512, SkNormDotsWP<8, 3>{}, (const float *)x, (const float *)nwA, y, (const float *)streams, (const float *)FA[c % cf], d)); };
        auto N = [&](int, EvV &ev) { ev.push_back(wgl<32>(q, 1, 512, SkNormW<5120, 16>{}, (const float *)x, (const float *)nwA, y)); };
        auto D1 = [&](int c, EvV &ev) { ev.push_back(wgl<64>(q, 1, 512, DotsK{0}, (const float *)streams, (const float *)FA[c % cf], d)); };
        auto D25 = [&](int c, EvV &ev) { ev.push_back(wgl<64>(q, 25, 512, DotsK{0}, (const float *)streams, (const float *)FA[c % cf], d)); };
        auto D25P1 = [&](int c, EvV &ev) { ev.push_back(wgl<64>(q, 25, 512, DotsKP<1>{0}, (const float *)streams, (const float *)FA[c % cf], d)); };
        auto RW = [&](auto rpw, int c, EvV &ev) {
            constexpr unsigned P = decltype(rpw)::value;
            ev.push_back(wgl<1>(q, NE / P, 32 * P, RouterRowsK<P>{}, (const uint8_t *)RT[c % cr], (const float *)yr, router));
        };
        auto DP = [&](auto spw, unsigned rows, int c, EvV &ev) {
            constexpr unsigned P = decltype(spw)::value;
            ev.push_back(wgl<1>(q, rows * (16 / P), 32 * P, DotsPartK<P>{}, (const float *)streams, (const float *)FA[c % cf], part));
        };
        auto R = [&](int c, EvV &ev) { ev.push_back(rows0(q, NE, GemvH16P<160, Act>{NE}, (const uint8_t *)RT[c % cr], (const float *)yr, router)); };
        auto RN = [&](int c, EvV &ev) {
            using K = FlNormK<5120, 16, 0, 8, 0, NoRows, FR>;
            ev.push_back(flk(q, K{x, nwF, y, streams, FF[c % cf], d, NoRows{}, FR{NE, RT[c % cr], router}}, 5120));
        };
        auto F = [&](int c, EvV &ev) {
            using K = FlNormK<5120, 16, 25, 8, 0, NoRows, FR>;
            ev.push_back(flk(q, K{x, nwF, y, streams, FF[c % cf], d, NoRows{}, FR{NE, RT[c % cr], router}}, 5120));
        };
        auto RNP = [&](auto hint, int c, EvV &ev) {
            using K = FlNormKP<5120, 16, 0, 8, 0, 160, decltype(hint)::value, 0>;
            ev.push_back(flk(q, K{x, nwF, y, streams, FF[c % cf], d, NoRows{}, FR{NE, RT[c % cr], router}}, 5120));
        };
        auto FP = [&](auto hint, auto pd, int c, EvV &ev) {
            using K = FlNormKP<5120, 16, 25, 8, 0, 160, decltype(hint)::value, decltype(pd)::value>;
            ev.push_back(flk(q, K{x, nwF, y, streams, FF[c % cf], d, NoRows{}, FR{NE, RT[c % cr], router}}, 5120));
        };
        using I1 = std::integral_constant<int, 1>;
        using I3 = std::integral_constant<int, 3>;
        using Z0 = std::integral_constant<int, 0>;
        // ---- bitwise: every form against production, each set on a hot and a cold copy
        std::mt19937 g(31337u + L);
        for (int si = 0; si < nset; ++si) {
            fill(q, x, H, g, si % 2 ? 1.0f : 0.5f, 30.f);
            fill(q, streams, H4, g, si == nset - 1 ? 1.0f : 0.6f, 30.f);
            fill(q, yr, H, g, 0.05f, 10.f);
            for (int c : {0, ccold - 1}) {
                auto grab = [&](std::function<void(int, EvV &)> f, bool rt_) {
                    q.memset(y, 0xff, H * 4), q.memset(d, 0xff, 1600), q.memset(router, 0xff, NE * 4), q.wait();
                    EvV ev;
                    f(c, ev);
                    q.wait();
                    auto v = words(q, y, H), dv = words(q, d, 400);
                    v.insert(v.end(), dv.begin(), dv.end());
                    if (rt_) { auto r = words(q, router, NE); v.insert(v.end(), r.begin(), r.end()); }
                    return v;
                };
                const auto a0 = grab(A, false);
                const std::string cs = " (set " + std::to_string(si) + ", copy " + std::to_string(c) + ")";
                check("AP1" + cs, a0, grab(AP1, false));
                check("AP3" + cs, a0, grab(AP3, false));
                auto dd = grab(D25, false), dp = grab(D25P1, false);
                check("D25P1" + cs, dd, dp);
                const auto f0 = grab(F, true);
                check("FP1" + cs, f0, grab([&](int c_, EvV &ev) { FP(I1{}, Z0{}, c_, ev); }, true));
                check("FP3" + cs, f0, grab([&](int c_, EvV &ev) { FP(I3{}, Z0{}, c_, ev); }, true));
                check("FPD1" + cs, f0, grab([&](int c_, EvV &ev) { FP(I1{}, I1{}, c_, ev); }, true));
                check("FPD3" + cs, f0, grab([&](int c_, EvV &ev) { FP(I3{}, I3{}, c_, ev); }, true));
                // RN / RNP: y and the logits (no dot rows: the partials stay as cleared)
                const auto r0 = grab(RN, true);
                check("RNP1" + cs, r0, grab([&](int c_, EvV &ev) { RNP(I1{}, c_, ev); }, true));
                check("RNP3" + cs, r0, grab([&](int c_, EvV &ev) { RNP(I3{}, c_, ev); }, true));
                // the router rows at 16 / 8 / 4 / 1 rows per work-group: the same logits
                {
                    auto rl = [&](std::function<void(int, EvV &)> f) {
                        q.memset(router, 0xff, NE * 4).wait();
                        EvV ev;
                        f(c, ev);
                        q.wait();
                        return words(q, router, NE);
                    };
                    const auto l16 = rl(R);
                    check("R8" + cs, l16, rl([&](int c_, EvV &ev) { RW(std::integral_constant<unsigned, 8>{}, c_, ev); }));
                    check("R4" + cs, l16, rl([&](int c_, EvV &ev) { RW(std::integral_constant<unsigned, 4>{}, c_, ev); }));
                    check("R1" + cs, l16, rl([&](int c_, EvV &ev) { RW(std::integral_constant<unsigned, 1>{}, c_, ev); }));
                }
                // the FFN launch's logits equal RN's (the dot rows do not touch them)
                {
                    std::vector<uint32_t> a(f0.end() - NE, f0.end()), b(r0.end() - NE, r0.end());
                    check("F vs RN logits" + cs, a, b);
                }
            }
        }
        std::printf("bitwise layer %u: %ld comparisons, %d differ\n", L, g_cmp, g_fail);
        if (!notime) {
            std::vector<Var> all;
            auto add = [&](const std::string &n, std::function<void(int, EvV &)> f) {
                if (only && n.find(only) == std::string::npos) return;
                all.push_back({n, f, ccold});
                all.push_back({n, f, 1});
            };
            add("E1", [&](int, EvV &ev) { ev.push_back(empty(q, 1)); });
            add("E26", [&](int, EvV &ev) { ev.push_back(empty(q, 26)); });
            add("E49", [&](int, EvV &ev) { ev.push_back(empty(q, 49)); });
            add("N", N);
            add("D1", D1);
            add("D25", D25);
            add("D25P1", D25P1);
            using U16 = std::integral_constant<unsigned, 16>;
            using U8 = std::integral_constant<unsigned, 8>;
            using U4 = std::integral_constant<unsigned, 4>;
            using U1 = std::integral_constant<unsigned, 1>;
            add("DP16x1", [&](int c, EvV &ev) { DP(U16{}, 1, c, ev); });
            add("DP8x1", [&](int c, EvV &ev) { DP(U8{}, 1, c, ev); });
            add("DP4x1", [&](int c, EvV &ev) { DP(U4{}, 1, c, ev); });
            add("DP16x25", [&](int c, EvV &ev) { DP(U16{}, 25, c, ev); });
            add("DP8x25", [&](int c, EvV &ev) { DP(U8{}, 25, c, ev); });
            add("DP4x25", [&](int c, EvV &ev) { DP(U4{}, 25, c, ev); });
            add("A", A);
            add("AP1", AP1);
            add("AP3", AP3);
            add("R", R);
            add("R8", [&](int c, EvV &ev) { RW(U8{}, c, ev); });
            add("R4", [&](int c, EvV &ev) { RW(U4{}, c, ev); });
            add("R1", [&](int c, EvV &ev) { RW(U1{}, c, ev); });
            add("RN", RN);
            add("RNP1", [&](int c, EvV &ev) { RNP(I1{}, c, ev); });
            add("RNP3", [&](int c, EvV &ev) { RNP(I3{}, c, ev); });
            add("F", F);
            add("FP1", [&](int c, EvV &ev) { FP(I1{}, Z0{}, c, ev); });
            add("FP3", [&](int c, EvV &ev) { FP(I3{}, Z0{}, c, ev); });
            add("FPD1", [&](int c, EvV &ev) { FP(I1{}, I1{}, c, ev); });
            add("FPD3", [&](int c, EvV &ev) { FP(I3{}, I3{}, c, ev); });
            if (!all.empty()) time_vars(q, all, reps, rounds, (int)L);
        }
        for (auto *f : FA) sycl::free(f, q);
        for (auto *f : FF) sycl::free(f, q);
        for (auto *f : RT) sycl::free(f, q);
        sycl::free(nwA, q), sycl::free(nwF, q);
    }
    std::printf("\nALL: %ld comparisons, %d differ: %s\n", g_cmp, g_fail, g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
