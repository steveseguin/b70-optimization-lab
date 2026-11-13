// bench_lat.cpp (rep2 helper, 2026-11-13; dots/README.md sections 5-6): one card.
//  (1) dependent-op latencies, one sub-group (ns per op): F32 add, F64 add / mul / div / sqrt, F32 and F64 xor shuffle +
//      add, float -> double -> add, the dot's TwoSum element (float), a 16-sub-group barrier round trip
//  (2) read floors: a plain streaming read of 1.97 MB / 5.90 MB windows of a cold buffer over 32..256 work-groups
//  (3) the dot work-group's tail: DT0 = chains + barrier + SkDotsFF's tree (no check), DT1 = + the check (no fallback
//      code), D = SkDotsFF (production), DT = SkDotsFT (form T1); 1 and 25 rows; A = SkNormDotsW<8>, AT = SkNormDotsWT<8>
// Bitwise: AT vs A and DT vs D (y + all 200 partial words) on 4 input sets (the 4th: zero streams, every row takes the
// production partials), hot and cold copies. Timing inputs: nonzero streams (every row proven); "Dx25 zero" = zero
// streams (every row takes the production partials).  env: REPS=40 ROUNDS=5
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
#include "gguf_part.inc"

static constexpr unsigned H = 5120, H4 = 4 * H;
using EvV = std::vector<sycl::event>;

template <int OP> struct LatK {
    int iters;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const double *in, double *out, uint32_t *lm) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), sgi = sg.get_group_linear_id();
        double x = in[lane], y = in[32 + lane];
        float xf = (float)x, yf = (float)y, lo = 0;
#pragma unroll 8
        for (int i = 0; i < iters; ++i) {
            if constexpr (OP == 0) xf = xf + yf;
            if constexpr (OP == 1) x = x + y;
            if constexpr (OP == 2) x = x * y;
            if constexpr (OP == 3) x = y / x;
            if constexpr (OP == 4) x = sycl::sqrt(x);
            if constexpr (OP == 5) x = sycl::select_from_group(sg, x, (int)lane ^ 1) + y;
            if constexpr (OP == 6) xf = sycl::select_from_group(sg, xf, (int)lane ^ 1) + yf;
            if constexpr (OP == 7) x = double(float(x)) + y;
            if constexpr (OP == 8) { // the dot's TwoSum element on (hi = xf, lo)
                const float p = yf * yf;
                const float e = sycl::fma(yf, yf, -p);
                const float t = xf + p;
                const float z = t - xf;
                const float er = (xf - (t - z)) + (p - z);
                xf = t;
                lo = lo + (er + e);
            }
            if constexpr (OP == 9) { // barrier round trip over 16 sub-groups
                if (lane == 0) sk_put(lm, (int)sgi, x);
                sycl::group_barrier(it.get_group());
                x = x + sk_get(lm, (int)((sgi + 1) & 15));
                sycl::group_barrier(it.get_group());
            }
            if constexpr (OP == 10) x = sycl::select_from_group(sg, x, (int)lane ^ 16) + y;
            if constexpr (OP == 11) x = sycl::select_from_group(sg, x, 0) + y; // broadcast
        }
        out[it.get_global_linear_id()] = x + xf + lo;
    }
};
struct HeatK { // compute load to raise the card's clock before a latency pair
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const double *in, double *out, uint32_t *) const {
        float a[8];
        for (int j = 0; j < 8; ++j) a[j] = (float)in[j] + j;
        for (int i = 0; i < 4096; ++i)
#pragma unroll
            for (int j = 0; j < 8; ++j) a[j] = sycl::fma(a[j], 0.999f, 0.001f);
        float s = 0;
        for (int j = 0; j < 8; ++j) s += a[j];
        if (s == 12345.f) out[0] = s;
    }
};
struct BwK { // n1 floats from a, every sub-group a 1 KB block at a time, strided over all sub-groups
    size_t nblk;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *a, float *out, uint32_t *) const {
        sycl::sub_group sg = it.get_sub_group();
        const size_t gid = it.get_group_linear_id() * (it.get_local_range(0) / 32) + sg.get_group_linear_id();
        const size_t nsg = it.get_group_range(0) * (it.get_local_range(0) / 32);
        float s = 0;
        for (size_t c = gid; c < nblk; c += nsg) {
            const auto v = sg_bloadN<8>(sg, a + c * 256);
#pragma unroll
            for (int m = 0; m < 8; ++m) s += v[m];
        }
        if (sg.get_local_linear_id() == 0) out[gid] = s;
    }
};
// tail decomposition: SkDotsFF<8>'s chains (copied), then MODE 0: barrier + its tree, write T; MODE 1: + the check
template <int MODE> struct DtK {
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *streams, const float *fn, double *out, uint32_t *lm) const {
        using F = SkDotsFF<8>;
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), sgi = sg.get_group_linear_id(), r = (unsigned)it.get_group_linear_id();
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
        if (lane == 0) {
            sk_put(lm, (int)sgi, acc);
            lm[2 * F::SGS + sgi] = sycl::bit_cast<uint32_t>(ef);
        }
        sycl::group_barrier(it.get_group());
        double T = lane < F::SGS ? sk_get(lm, (int)lane) : 0.0;
        float E = lane < F::SGS ? sycl::bit_cast<float>(lm[2 * F::SGS + lane]) : 0.0f;
        for (int w = 1; w < 32; w <<= 1) {
            T += sycl::select_from_group(sg, T, (int)lane ^ w);
            E += sycl::select_from_group(sg, E, (int)lane ^ w);
        }
        T = sycl::select_from_group(sg, T, 0);
        E = sycl::select_from_group(sg, E, 0);
        if constexpr (MODE == 0) {
            if (sgi == 0 && lane == 0) out[r * F::SEG] = T + double(E);
        } else {
            if (F::check(r, T, E)) {
                if (sgi == 0 && lane < F::SEG) out[r * F::SEG + lane] = lane == 0 ? T : 0.0;
                return;
            }
            if (sgi == 0 && lane == 0) out[r * F::SEG] = NAN;
        }
    }
};
template <int FORM> struct DotsK { // FORM 0: SkDotsFF<8> (production), 1: SkDotsFT<8>
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *streams, const float *fn, double *out, uint32_t *lm) const {
        const unsigned sgi = it.get_sub_group().get_group_linear_id(), r = (unsigned)it.get_group_linear_id();
        if constexpr (FORM == 0) SkDotsFF<8>::run(it, sgi, lm, r, streams, fn, out);
        else SkDotsFT<8>::run(it, sgi, lm, r, streams, fn, out);
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
    std::normal_distribution<float> nd(0.f, sd > 0 ? sd : 1.f);
    std::uniform_real_distribution<float> u(0.f, 1.f);
    std::vector<float> v(n);
    for (auto &f : v) { f = sd > 0 ? nd(g) : 0.f; if (u(g) < 0.002f) f *= big; }
    q.memcpy(p, v.data(), n * 4).wait();
}
struct Var {
    std::string name;
    std::function<void(int c, EvV &ev)> f;
    int ncopy;
};
static void time_vars(sycl::queue &q, std::vector<Var> &vars, int reps, int rounds) {
    std::vector<std::vector<double>> t(vars.size());
    { EvV ev; for (int r = 0; r < 200; ++r) vars[0].f(r % vars[0].ncopy, ev); q.wait(); }
    for (int rd = 0; rd < rounds; ++rd)
        for (size_t kk = 0; kk < vars.size(); ++kk) {
            const size_t k = rd % 2 ? vars.size() - 1 - kk : kk;
            EvV ev;
            for (int r = 0; r < reps; ++r) vars[k].f((r + rd * 7) % vars[k].ncopy, ev);
            q.wait();
            for (int r = 1; r < reps; ++r) t[k].push_back(ev_us(ev[(size_t)r]));
        }
    for (size_t v = 0; v < vars.size(); ++v) {
        auto s = t[v];
        std::sort(s.begin(), s.end());
        std::printf("  T %-12s %-4s %7.2f  [%6.2f %6.2f]\n", vars[v].name.c_str(), vars[v].ncopy > 1 ? "cold" : "hot", median(t[v]),
                    s[s.size() / 10], s[s.size() * 9 / 10]);
    }
}

int main() {
    const int reps = envi("REPS", 40), rounds = envi("ROUNDS", 5);
    sycl::queue q{sycl::gpu_selector_v, sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const auto dev = q.get_device();
    const size_t l2 = dev.get_info<sycl::info::device::global_mem_cache_size>();
    std::printf("device %s, %u compute units, cache %.1f MiB, fp64 %d, max clock %u MHz\n", dev.get_info<sycl::info::device::name>().c_str(),
                dev.get_info<sycl::info::device::max_compute_units>(), l2 / 1048576.0, (int)dev.has(sycl::aspect::fp64),
                dev.get_info<sycl::info::device::max_clock_frequency>());
    if (!dev.has(sycl::aspect::ext_intel_free_memory)) { std::printf("free memory query unavailable\n"); return 3; }
    const size_t fm = dev.get_info<sycl::ext::intel::info::device::free_memory>();
    std::printf("free card memory %.2f GiB\n", fm / 1073741824.0);
    if (fm < ((size_t)4 << 30)) { std::printf("not enough free card memory\n"); return 3; }

    // ---- (1) latencies, first right after start, then with the clock raised
    for (int warm = 0; warm < 2; ++warm) {
        double *in = sycl::malloc_device<double>(64, q), *out = sycl::malloc_device<double>(512, q);
        std::vector<double> hin(64);
        for (int i = 0; i < 32; ++i) hin[i] = 1.5 + i * 1e-3, hin[32 + i] = 1.0 + 1e-9 * i;
        q.memcpy(in, hin.data(), 64 * 8).wait();
        const char *names[12] = {"f32 add", "f64 add", "f64 mul", "f64 div", "f64 sqrt", "f64 xor1 shuffle+add", "f32 xor1 shuffle+add",
                                 "f2d+add", "TwoSum element (f32)", "barrier round trip (2 barriers, 16 sg)", "f64 xor16 shuffle+add", "f64 broadcast+add"};
        std::printf("\n(1) dependent-op latency, ns per op (one sub-group; median of %d; (t(2304) - t(256)) / 2048)%s:\n", 9,
                    warm ? ", each pair right after 4 compute-load launches (clock up)" : "");
        auto lat = [&](auto op) {
            constexpr int OP = decltype(op)::value;
            const size_t wg = OP == 9 ? 512 : 32;
            std::vector<double> d;
            for (int rep = 0; rep < 9; ++rep) {
                if (warm) for (int h = 0; h < 4; ++h) wgl<1>(q, 256, 512, HeatK{}, (const double *)in, out);
                auto e1 = wgl<64>(q, 1, wg, LatK<OP>{256}, (const double *)in, out);
                auto e2 = wgl<64>(q, 1, wg, LatK<OP>{2304}, (const double *)in, out);
                q.wait();
                d.push_back((ev_us(e2) - ev_us(e1)) * 1000.0 / 2048);
            }
            std::printf("  L %-42s %7.2f ns\n", names[OP], median(d));
        };
        lat(std::integral_constant<int, 0>{}), lat(std::integral_constant<int, 1>{}), lat(std::integral_constant<int, 2>{});
        lat(std::integral_constant<int, 3>{}), lat(std::integral_constant<int, 4>{}), lat(std::integral_constant<int, 5>{});
        lat(std::integral_constant<int, 6>{}), lat(std::integral_constant<int, 7>{}), lat(std::integral_constant<int, 8>{});
        lat(std::integral_constant<int, 9>{}), lat(std::integral_constant<int, 10>{}), lat(std::integral_constant<int, 11>{});
        sycl::free(in, q), sycl::free(out, q);
    }

    // ---- (2) + (3)
    const std::string p = "blk.0.";
    const auto fa = f32_vec(p + "hc_attn_fn.weight", (size_t)24 * H4);
    const int cf = (int)((3 * l2) / (fa.size() * 4) + 1);
    std::vector<float *> FA;
    for (int c = 0; c < cf; ++c) FA.push_back(dcopy(q, fa));
    float *nwA = dcopy(q, f32_vec(p + "attn_norm.weight", H));
    float *x = sycl::malloc_device<float>(H, q), *y = sycl::malloc_device<float>(H, q), *streams = sycl::malloc_device<float>(H4, q);
    double *d = sycl::malloc_device<double>(200, q);
    const size_t S3 = 5898240 / 4, S1 = 1966080 / 4; // floats in a 5.90 MB / 1.97 MB window
    const int nb = (int)((3 * l2) / (S3 * 4) + 2);
    float *big = sycl::malloc_device<float>(S3 * nb, q), *bo = sycl::malloc_device<float>(256 * 16, q);
    q.memset(big, 0, S3 * nb * 4).wait();
    const int nb1 = (int)(S3 * nb / S1);
    std::printf("\nfn rows 1966080 B x %d copies; read-floor buffer %d x 5.90 MB\n", cf, nb);

    auto A = [&](int c, EvV &ev) { ev.push_back(wgl<64>(q, 26, 512, SkNormDotsW<8>{}, (const float *)x, (const float *)nwA, y, (const float *)streams, (const float *)FA[c % cf], d)); };
    auto AT = [&](int c, EvV &ev) { ev.push_back(wgl<64>(q, 26, 512, SkNormDotsWT<8>{}, (const float *)x, (const float *)nwA, y, (const float *)streams, (const float *)FA[c % cf], d)); };
    auto Dn = [&](auto form, unsigned rows, int c, EvV &ev) { ev.push_back(wgl<64>(q, rows, 512, DotsK<decltype(form)::value>{}, (const float *)streams, (const float *)FA[c % cf], d)); };
    auto DT = [&](auto mode, unsigned rows, int c, EvV &ev) { ev.push_back(wgl<64>(q, rows, 512, DtK<decltype(mode)::value>{}, (const float *)streams, (const float *)FA[c % cf], d)); };
    using I0 = std::integral_constant<int, 0>;
    using I1 = std::integral_constant<int, 1>;

    std::mt19937 g(4242u);
    for (int si = 0; si < 4; ++si) {
        fill(q, x, H, g, si % 2 ? 1.0f : 0.5f, 30.f);
        fill(q, streams, H4, g, si == 3 ? 0.0f : (si == 2 ? 1.0f : 0.6f), 30.f);
        for (int c : {0, cf - 1}) {
            auto grab = [&](std::function<void(int, EvV &)> f) {
                q.memset(y, 0xff, H * 4), q.memset(d, 0xff, 1600), q.wait();
                EvV ev;
                f(c, ev);
                q.wait();
                auto v = words(q, y, H), dv = words(q, d, 400);
                v.insert(v.end(), dv.begin(), dv.end());
                return v;
            };
            const std::string cs = " (set " + std::to_string(si) + ", copy " + std::to_string(c) + ")";
            check("AT" + cs, grab(A), grab(AT));
            check("D25T" + cs, grab([&](int c_, EvV &ev) { Dn(I0{}, 25, c_, ev); }), grab([&](int c_, EvV &ev) { Dn(I1{}, 25, c_, ev); }));
        }
    }
    std::printf("bitwise: %ld comparisons, %d differ\n", g_cmp, g_fail);

    fill(q, x, H, g, 0.5f, 30.f);
    fill(q, streams, H4, g, 0.6f, 30.f); // timing inputs: every row proven (the fast path, as ~99 % of launches)
    float *zs = sycl::malloc_device<float>(H4, q);
    q.memset(zs, 0, H4 * 4).wait();
    std::vector<Var> all;
    auto add = [&](const std::string &n, std::function<void(int, EvV &)> f, int ncold) {
        all.push_back({n, f, ncold});
        all.push_back({n, f, 1});
    };
    for (unsigned wgs : {32u, 64u, 128u, 256u}) {
        add("BW1@" + std::to_string(wgs), [&, wgs](int c, EvV &ev) { ev.push_back(wgl<1>(q, wgs, 512, BwK{S1 / 256}, (const float *)big + (size_t)c * S1, bo)); }, nb1);
        add("BW3@" + std::to_string(wgs), [&, wgs](int c, EvV &ev) { ev.push_back(wgl<1>(q, wgs, 512, BwK{S3 / 256}, (const float *)big + (size_t)c * S3, bo)); }, nb);
    }
    for (unsigned rows : {1u, 25u}) {
        const std::string rs = std::to_string(rows);
        add("DT0x" + rs, [&, rows](int c, EvV &ev) { DT(I0{}, rows, c, ev); }, cf);
        add("DT1x" + rs, [&, rows](int c, EvV &ev) { DT(I1{}, rows, c, ev); }, cf);
        add("Dx" + rs, [&, rows](int c, EvV &ev) { Dn(I0{}, rows, c, ev); }, cf);
        add("DTx" + rs, [&, rows](int c, EvV &ev) { Dn(I1{}, rows, c, ev); }, cf);
    }
    add("A", A, cf);
    add("AT", AT, cf);
    add("Dx25 zero", [&](int c, EvV &ev) { ev.push_back(wgl<64>(q, 25, 512, DotsK<0>{}, (const float *)zs, (const float *)FA[c % cf], d)); }, cf);

    std::printf("\ntiming (%d rounds x %d reps, kernel us: median [p10 p90]):\n", rounds, reps - 1);
    time_vars(q, all, reps, rounds);
    std::printf("\nALL: %ld comparisons, %d differ: %s\n", g_cmp, g_fail, g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
