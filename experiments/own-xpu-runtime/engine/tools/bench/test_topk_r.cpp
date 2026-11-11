// TopKSelR (the final walk by ranges, OWN_TOPK_R) against TopKSelP (the walk in steps of 1,024), bit for bit, and
// GPU time of each, on one card: the plain select (top 512 of n, offset 128), the masked select (a mask from the
// block select), and the block select (block 8, top 2048, newest pinned; mask rows and block list), at the
// engine's lengths. Score arrays: normal values, a few values (heavy ties), +0 / -0, mostly -inf, and NaNs of
// both signs mixed in.
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/test_topk_r.cpp -o test_topk_r
#include <sycl/sycl.hpp>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const int MAXN = 140000;
    float *sc = sycl::malloc_device<float>(MAXN + 64, q);
    uint8_t *ca = sycl::malloc_device<uint8_t>(MAXN + 64, q), *cb = sycl::malloc_device<uint8_t>(MAXN + 64, q);
    int32_t *la = sycl::malloc_device<int32_t>(2048 + 64, q), *lb = sycl::malloc_device<int32_t>(2048 + 64, q);
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
    long bad = 0;
    auto cmp = [&](size_t nl, size_t nc) {
        std::vector<int32_t> x(nl), y(nl);
        std::vector<uint8_t> u(nc), v(nc);
        q.memcpy(x.data(), la, nl * 4);
        q.memcpy(y.data(), lb, nl * 4);
        if (nc) { q.memcpy(u.data(), ca, nc); q.memcpy(v.data(), cb, nc); }
        q.wait();
        return x == y && u == v;
    };
    std::printf("%-18s %7s | %9s %9s %5s | %9s %9s %5s | %9s %9s %5s\n", "scores", "n", "sel P us", "sel R us", "same",
                "mask P", "mask R", "same", "block P", "block R", "same");
    for (int kind = 0; kind < 5; ++kind)
        for (int n : {600, 2300, 4700, 17000, 19000, 34000, 69000, 95000, 130000}) {
            fill(n, kind);
            const int nb = (n + 7) / 8;
            double t[6] = {};
            bool s1 = true, s2 = true, s3 = true;
            const int REP = kind == 0 ? 10 : 1;
            for (int r = 0; r < REP + (kind == 0); ++r) {
                // block select: mask rows + block list (P with the list, as OWN_IDX_CAND runs it)
                q.fill(ca, (uint8_t)7, MAXN + 64);
                q.fill(cb, (uint8_t)7, MAXN + 64);
                q.fill(la, -5, 2048 + 64);
                q.fill(lb, -5, 2048 + 64);
                auto e4 = local(KB{nb, 2048, 0, 0, 0, 8, n}, (const float *)sc, (const uint8_t *)nullptr, la, ca);
                auto e5 = local(TopKSelR<true>{KB{nb, 2048, 0, 0, 0, 8, n}}, (const float *)sc, (const uint8_t *)nullptr, lb, cb);
                q.wait();
                s3 = s3 && cmp(2049, (size_t)n);
                // plain select
                q.fill(la, -5, 2048 + 64);
                q.fill(lb, -5, 2048 + 64);
                auto e0 = local(KR{n, 512, 128, 512, 0, 0, 0}, (const float *)sc, (const uint8_t *)nullptr, la, (uint8_t *)nullptr);
                auto e1 = local(TopKSelR<false>{KR{n, 512, 128, 512, 0, 0, 0}}, (const float *)sc, (const uint8_t *)nullptr, lb,
                                (uint8_t *)nullptr);
                q.wait();
                s1 = s1 && cmp(512, 0);
                // masked select with the block select's mask (ca)
                q.fill(la, -5, 2048 + 64);
                q.fill(lb, -5, 2048 + 64);
                auto e2 = local(KR{n, 512, 128, 512, n, 0, 0}, (const float *)sc, (const uint8_t *)ca, la, (uint8_t *)nullptr);
                auto e3 = local(TopKSelR<false>{KR{n, 512, 128, 512, n, 0, 0}}, (const float *)sc, (const uint8_t *)ca, lb,
                                (uint8_t *)nullptr);
                q.wait();
                s2 = s2 && cmp(512, 0);
                if (r || kind != 0) { t[0] += us(e0); t[1] += us(e1); t[2] += us(e2); t[3] += us(e3); t[4] += us(e4); t[5] += us(e5); }
            }
            for (auto &x : t) x /= REP;
            bad += !s1 + !s2 + !s3;
            std::printf("%-18s %7d | %9.1f %9.1f %5s | %9.1f %9.1f %5s | %9.1f %9.1f %5s\n", kinds[kind], n, t[0], t[1],
                        s1 ? "yes" : "NO", t[2], t[3], s2 ? "yes" : "NO", t[4], t[5], s3 ? "yes" : "NO");
        }
    std::printf(bad ? "FAIL (%ld differ)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
