// The engram gate (EngramGateP, layers 1 and 14: 116 us per launch, three serial double chains of h - 1 adds per
// stream) against its fast bracket (OWN_ENG_FF, EngramGateP::fast in sycl_v41.hpp). Bulk check: many sets per
// input pattern, every set's four updated streams compared BITWISE between the chain form and the fast form, and
// the number of streams where the bracket could not decide (the chains ran). Timing: one set (one launch of four
// sub-groups, as in the engine), the forms back to back, interleaved. C / D: the work-group form (EngramGateW: the
// bracket's sums over 16 / 8 sub-groups per stream, the chains on sub-group 0 when it cannot decide), checked the
// same way against the chains.
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_engram_ff.cpp -o $S/bench_engram_ff
//   ONEAPI_DEVICE_SELECTOR=level_zero:1 $S/bench_engram_ff
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

static constexpr int H = 5120;
static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
// set s's stream j in work-group 4 s + j (streams 4H per set, kv 5H per set, gate 4H per set)
struct EngSets {
    EngramGateP k;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, float *streams, const float *kv, const float *gw, int *und) const {
        sycl::sub_group sg = it.get_sub_group();
        const size_t g = it.get_group_linear_id(), s = g / 4;
        const int j = (int)(g % 4), lane = (int)sg.get_local_linear_id();
        float *st = streams + s * 4 * H;
        const float *kb = kv + s * 5 * H, *gb = gw + s * 4 * H;
        if (und) { // the bracket's verdict only
            float r = 0, d = 0;
            const bool ok = k.fast(sg, lane, st + (size_t)j * H, kb + (size_t)j * H, gb + (size_t)j * H, 1e-20f, r, d);
            if (lane == 0) und[g] = ok ? 0 : 1;
            return;
        }
        k.run(sg, lane, j, st, kb, gb);
    }
};

template <unsigned S> struct EngSetsW {
    EngramGateP k;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, float *streams, const float *kv, const float *gw, uint32_t *lm) const {
        const size_t g = it.get_group_linear_id(), s = g / 4;
        k.run_wg<S>(it, (int)(g % 4), streams + s * 4 * H, kv + s * 5 * H, gw + s * 4 * H, lm);
    }
};

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    std::mt19937 rng(17);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::uniform_real_distribution<float> uu(0.f, 1.f);
    constexpr int NS = 4096, NP = 14;
    const char *pats[NP] = {"random", "magnitudes 2^+-28 per vector", "sparse (99 % zero)", "one huge value",
                            "constant", "dot cancels exactly (pairs)", "streams all zero", "keys all zero",
                            "tiny (subnormal floats)", "large (~1e30)", "an inf in a stream", "a NaN in a key",
                            "quantized (ties)", "dot nearly cancels (gate signs alternate)"};
    const size_t NSt = (size_t)NS * 4 * H, NKv = (size_t)NS * 5 * H;
    std::vector<float> hs(NSt), hk(NKv), hg(NSt);
    float *st0 = sycl::malloc_device<float>(NSt, q), *st1 = sycl::malloc_device<float>(NSt, q);
    float *kv = sycl::malloc_device<float>(NKv, q), *gw = sycl::malloc_device<float>(NSt, q);
    int *und = sycl::malloc_device<int>((size_t)NS * 4, q);
    std::vector<float> o0(NSt), o1(NSt);
    std::vector<int> hu((size_t)NS * 4);
    long bad = 0, und_all = 0, und_fin = 0, n_all = 0;
    auto launch = [&](EngramGateP k, float *st, int *u, size_t sets) {
        EngSets ks{k};
        return q.parallel_for(sycl::nd_range<1>(sets * 4 * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            ks(it, st, kv, gw, u);
        });
    };
    auto launchw = [&](auto ks, size_t S, float *st, size_t sets) {
        return q.submit([&](sycl::handler &hh) {
            sycl::local_accessor<uint32_t, 1> lt(8 * 16 + 2, hh);
            hh.parallel_for(sycl::nd_range<1>(sets * 4 * 32 * S, 32 * S), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                ks(it, st, kv, gw, &lt[0]);
            });
        });
    };
    float *st2 = sycl::malloc_device<float>(NSt, q), *st3 = sycl::malloc_device<float>(NSt, q);
    std::vector<float> o2(NSt), o3(NSt);
    EngramGateP kc{H}, kf{H};
    kc.ff = false;
    kf.ff = true;
    for (int pat = 0; pat < NP; ++pat) {
        for (int s = 0; s < NS; ++s) {
            float *S = &hs[(size_t)s * 4 * H], *K = &hk[(size_t)s * 5 * H], *G = &hg[(size_t)s * 4 * H];
            const float ms = std::ldexp(1.0f, (int)(uu(rng) * 56) - 28), mk = std::ldexp(1.0f, (int)(uu(rng) * 56) - 28),
                        mg = std::ldexp(1.0f, (int)(uu(rng) * 56) - 28);
            for (int i = 0; i < 4 * H; ++i) {
                float a = nd(rng), b = nd(rng), c = 0.05f * nd(rng);
                if (pat == 1) { a *= ms; b *= mk; c *= mg; }
                if (pat == 2) { if (uu(rng) < 0.99f) a = 0; if (uu(rng) < 0.99f) b = 0; }
                if (pat == 4) { a = 0.75f; b = -1.25f; c = 0.125f; }
                if (pat == 6) a = 0;
                if (pat == 7) b = 0;
                if (pat == 8) { a *= 1e-40f; b *= 1e-41f; }
                if (pat == 9) { a *= 1e30f; b *= 1e29f; c *= 1e20f; }
                if (pat == 12) { a = std::round(a * 4) / 4; b = std::round(b * 4) / 4; c = std::round(c * 64) / 64; }
                if (pat == 13) c = std::fabs(c) * ((i & 1) ? -1.0f : 1.0f);
                S[i] = a;
                K[i] = b;
                G[i] = c;
            }
            for (int i = 4 * H; i < 5 * H; ++i) K[i] = nd(rng);
            if (pat == 3) S[(int)(uu(rng) * 4 * H) % (4 * H)] = 1e15f;
            if (pat == 5) // element 2m + 1 = -(element 2m) in the stream, the same key and gate: the dot is exactly 0
                for (int i = 0; i < 4 * H; i += 2) { S[i + 1] = -S[i]; K[i + 1] = K[i]; G[i + 1] = G[i]; }
            if (pat == 10) S[(int)(uu(rng) * 4 * H) % (4 * H)] = INFINITY;
            if (pat == 11) K[(int)(uu(rng) * 4 * H) % (4 * H)] = NAN;
        }
        q.memcpy(st0, hs.data(), NSt * 4);
        q.memcpy(st1, hs.data(), NSt * 4);
        q.memcpy(st2, hs.data(), NSt * 4);
        q.memcpy(st3, hs.data(), NSt * 4);
        q.memcpy(kv, hk.data(), NKv * 4);
        q.memcpy(gw, hg.data(), NSt * 4).wait();
        launch(kf, st0, und, NS).wait();
        launch(kc, st0, nullptr, NS);
        launch(kf, st1, nullptr, NS).wait();
        launchw(EngSetsW<16>{kf}, 16, st2, NS);
        launchw(EngSetsW<8>{kf}, 8, st3, NS).wait();
        q.memcpy(o0.data(), st0, NSt * 4);
        q.memcpy(o1.data(), st1, NSt * 4);
        q.memcpy(o2.data(), st2, NSt * 4);
        q.memcpy(o3.data(), st3, NSt * 4);
        q.memcpy(hu.data(), und, hu.size() * 4).wait();
        long d = 0, u = 0, d2 = 0, d3 = 0;
        for (size_t g = 0; g < (size_t)NS * 4; ++g) {
            d += std::memcmp(&o0[g * H], &o1[g * H], H * 4) != 0;
            d2 += std::memcmp(&o0[g * H], &o2[g * H], H * 4) != 0;
            d3 += std::memcmp(&o0[g * H], &o3[g * H], H * 4) != 0;
            u += hu[g];
        }
        std::printf("%-44s %6d streams: %ld differ (W16 %ld, W8 %ld), the chains ran for %ld\n", pats[pat], NS * 4, d,
                    d2, d3, u);
        bad += d + d2 + d3;
        und_all += u;
        n_all += (long)NS * 4;
        if (pat != 10 && pat != 11) und_fin += u;
    }
    std::printf("all patterns: %ld streams, %ld differ, chains ran for %ld (%ld outside the inf / NaN sets)\n", n_all, bad,
                und_all, und_fin);
    // timing: set 0 (random inputs), one launch of four sub-groups, back to back, interleaved
    {
        std::vector<float> hs1(4 * H), hk1(5 * H), hg1(4 * H);
        for (auto &v : hs1) v = nd(rng);
        for (auto &v : hk1) v = nd(rng);
        for (auto &v : hg1) v = 0.05f * nd(rng);
        q.memcpy(st0, hs1.data(), hs1.size() * 4);
        q.memcpy(st1, hs1.data(), hs1.size() * 4);
        q.memcpy(kv, hk1.data(), hk1.size() * 4);
        q.memcpy(gw, hg1.data(), hg1.size() * 4).wait();
    }
    q.memcpy(st2, st0, 4 * H * 4);
    q.memcpy(st3, st0, 4 * H * 4).wait();
    constexpr int NF = 4;
    std::vector<double> tm[NF];
    for (int set = 0; set < 8; ++set) {
        std::vector<std::pair<int, sycl::event>> evs;
        for (int r = 0; r < 26; ++r)
            for (int v = 0; v < NF; ++v) {
                auto e = v < 2 ? launch(v ? kf : kc, v ? st1 : st0, nullptr, 1)
                               : v == 2 ? launchw(EngSetsW<16>{kf}, 16, st2, 1) : launchw(EngSetsW<8>{kf}, 8, st3, 1);
                if (r) evs.push_back({v, e});
            }
        q.wait();
        for (auto &[v, e] : evs) tm[v].push_back(ev_us(e));
    }
    const char *names[NF] = {"A chains (OWN_ENG_FF=0)", "B fast bracket, one sub-group", "C work-group of 16 sub-groups",
                             "D work-group of 8 sub-groups"};
    std::printf("%-34s %10s %10s %10s %10s\n", "form", "median us", "min us", "p10 us", "p90 us");
    for (int v = 0; v < NF; ++v) {
        auto t = tm[v];
        std::sort(t.begin(), t.end());
        std::printf("%-34s %10.2f %10.2f %10.2f %10.2f\n", names[v], t[t.size() / 2], t[0], t[t.size() / 10], t[t.size() * 9 / 10]);
    }
    std::printf(bad ? "FAIL (%ld)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
