// q3: TopKSelQ (keys in registers) vs TopKSelP / TopKSelR. Where does the top-512 select's time go (TopKSelR, one work-group of 1,024, ~100 us at 69,000 rows)? Forms of
// TopKSelR<false> that keep its algorithm (the same four radix passes, the same walk by ranges, so the same
// list), each against TopKSelP bit for bit, GPU time of each on one card:
//   R        TopKSelR<false> (the engine, OWN_TOPK_R)
//   X<U,A>   loads issued U at a time (the passes over strided positions and the walk over the item's range),
//            A: the radix passes' local-memory adds folded per sub-group for the keys whose digit equals
//            lane 0's (one ballot and one add for all of them; the other lanes add as before)
// Score arrays as test_topk_r: normal values, a few values (heavy ties), +0 / -0, mostly -inf, NaNs mixed in;
// plain select (top 512 of n, offset 128) and masked select (the block select's mask).
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/test_topk_q.cpp -o test_topk_q
//   ONEAPI_DEVICE_SELECTOR=level_zero:1 ./test_topk_q
#include <sycl/sycl.hpp>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

#include "qsel.inc"

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    const int MAXN = 140000;
    float *sc = sycl::malloc_device<float>(MAXN + 64, q);
    uint8_t *ca = sycl::malloc_device<uint8_t>(MAXN + 64, q);
    constexpr int NV = 3;
    int32_t *ls[NV];
    for (auto &l : ls) l = sycl::malloc_device<int32_t>(2048 + 64, q);
    using KB = TopKSelP<true>;
    using KR = TopKSelP<false>;
    constexpr size_t SLM = (size_t)KR::NSG * 256 + 8;
    auto local = [&](auto k, auto... a) {
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(SLM, h);
            h.parallel_for(sycl::nd_range<1>(1024, 1024), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k(it, a..., &lt[0]);
            });
        });
    };
    auto us = [](sycl::event &e) {
        return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
    };
    std::mt19937 rng(5);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::vector<float> hs(MAXN);
    const char *kinds[5] = {"normal", "few values (ties)", "+0 / -0", "mostly -inf", "with NaNs"};
    auto fill = [&](int n, int kind) {
        for (int j = 0; j < n; ++j) {
            const float f = nd(rng);
            hs[j] = kind == 1 ? std::floor(f * 1.5f) : kind == 2 ? (f > 0 ? 0.0f : -0.0f) : kind == 3 ? -INFINITY : f;
        }
        if (kind == 3)
            for (int i = 0; i < 300; ++i) hs[(size_t)(rng() % n)] = nd(rng);
        if (kind == 4)
            for (int i = 0; i < 64; ++i) hs[(size_t)(rng() % n)] = (i & 1) ? std::nanf("") : -std::nanf("");
        q.memcpy(sc, hs.data(), (size_t)n * 4).wait();
    };
    const char *vn[NV] = {"P", "R", "Q"};
    auto run = [&](int v, const KR &k, const uint8_t *cand, int32_t *l) -> sycl::event {
        if (v == 0) return local(k, (const float *)sc, cand, l, (uint8_t *)nullptr);
        if (v == 1) return local(TopKSelR<false>{k}, (const float *)sc, cand, l, (uint8_t *)nullptr);
        const int c = TopKSelQ<16>::span(k.n);
        if (c <= 16) return local(TopKSelQ<16>{k}, (const float *)sc, cand, l, (uint8_t *)nullptr);
        if (c <= 32) return local(TopKSelQ<32>{k}, (const float *)sc, cand, l, (uint8_t *)nullptr);
        if (c <= 64) return local(TopKSelQ<64>{k}, (const float *)sc, cand, l, (uint8_t *)nullptr);
        return local(TopKSelQ<96>{k}, (const float *)sc, cand, l, (uint8_t *)nullptr);
    };
    long bad = 0;
    std::printf("%-18s %7s %6s |", "scores", "n", "select");
    for (auto s : vn) std::printf(" %9s", s);
    std::printf(" | same as P\n");
    for (int kind = 0; kind < 5; ++kind)
        for (int n : {600, 2300, 4700, 16391, 17000, 19000, 34000, 69000, 95497, 98304}) {
            fill(n, kind);
            const int nb = (n + 7) / 8;
            q.fill(ca, (uint8_t)7, MAXN + 64);
            q.fill(ls[0], -5, 2048 + 64);
            local(KB{nb, 2048, 0, 0, 0, 8, n}, (const float *)sc, (const uint8_t *)nullptr, ls[0], ca).wait();
            for (int masked = 0; masked < 2; ++masked) {
                const KR k{n, 512, 128, 512, masked ? n : 0, 0, 0};
                const uint8_t *cand = masked ? ca : nullptr;
                double t[NV] = {};
                bool same[NV];
                for (auto &s : same) s = true;
                const int REP = kind == 0 ? 10 : 2;
                for (int r = 0; r <= REP; ++r) {
                    for (int v = 0; v < NV; ++v) q.fill(ls[v], -5, 2048 + 64);
                    q.wait();
                    for (int v = 0; v < NV; ++v) {
                        auto e = run(v, k, cand, ls[v]);
                        e.wait();
                        if (r) t[v] += us(e);
                    }
                    std::vector<int32_t> ref(512), o(512);
                    q.memcpy(ref.data(), ls[0], 512 * 4).wait();
                    for (int v = 1; v < NV; ++v) {
                        q.memcpy(o.data(), ls[v], 512 * 4).wait();
                        if (o != ref) same[v] = false;
                    }
                }
                std::printf("%-18s %7d %6s |", kinds[kind], n, masked ? "masked" : "plain");
                for (int v = 0; v < NV; ++v) std::printf(" %9.1f", t[v] / REP);
                std::printf(" |");
                for (int v = 1; v < NV; ++v) {
                    std::printf(" %s", same[v] ? "y" : "NO");
                    bad += !same[v];
                }
                std::printf("\n");
            }
        }
    std::printf(bad ? "FAIL (%ld differ)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
