// IndexerScoreBMR<R> (R rows per item) against IndexerScoreBM (one row per item), bit for bit, and GPU time of
// each, for blocks of M tokens (the prompt reading's blocks of 16, the guess checks' 2-6) at long lengths.
// Token t of a block sees len0 + t / 4 compressed rows (ratio 4), as in the engine.
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/test_index_score_m.cpp -o test_index_score_m
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const int MAXN = 140000, MT = 16;
    const size_t SS = (size_t)MAXN + 64;
    float *dq = sycl::malloc_device<float>((size_t)MT * 4096, q), *dw = sycl::malloc_device<float>((size_t)MT * 32, q);
    uint16_t *dk = sycl::malloc_device<uint16_t>((size_t)MAXN * 128, q);
    float *sa = sycl::malloc_device<float>(MT * SS, q), *sb = sycl::malloc_device<float>(MT * SS, q);
    std::mt19937 rng(7);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::vector<float> hq((size_t)MT * 4096), hw((size_t)MT * 32);
    std::vector<uint16_t> hk((size_t)MAXN * 128);
    for (auto &v : hq) v = nd(rng) * 0.1f;
    for (auto &v : hw) v = nd(rng);
    for (auto &v : hk) {
        const float f = nd(rng);
        uint32_t u;
        std::memcpy(&u, &f, 4);
        v = (uint16_t)(u >> 16);
    }
    q.memcpy(dq, hq.data(), hq.size() * 4);
    q.memcpy(dw, hw.data(), hw.size() * 4);
    q.memcpy(dk, hk.data(), hk.size() * 2).wait();
    auto us = [](sycl::event &e) {
        return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
    };
    constexpr size_t WG = 128;
    long bad = 0;
    std::printf("%5s %7s %10s %10s %10s %10s  %s\n", "M", "len0", "BM us", "R2 us", "R4 us", "R8 us", "bitwise");
    for (int M : {16, 4, 1}) {
        for (int len0 : {700, 4300, 8600, 17000, 24000, 34000}) {
            int lens[16] = {};
            long lmax = 0;
            for (int t = 0; t < M; ++t) lens[t] = len0 + t / 4, lmax = std::max<long>(lmax, lens[t]);
            auto runBM = [&]() {
                IndexerScoreBM<ActF32> k{};
                for (int t = 0; t < M; ++t) k.lens[t] = lens[t];
                k.m = (unsigned)M;
                k.gpt = (unsigned)((((lmax + 31) / 32 * 32) + WG - 1) / WG);
                k.qs = 4096, k.ws = 32, k.ss = SS;
                return q.submit([&](sycl::handler &h) {
                    sycl::local_accessor<float, 1> lt(32 * 128 + 32, h);
                    h.parallel_for(sycl::nd_range<1>((size_t)M * k.gpt * WG, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                        k(it, dq, dk, dw, sa, &lt[0]);
                    });
                });
            };
            auto runR = [&](auto rc) {
                constexpr int R = decltype(rc)::value;
                IndexerScoreBMR<ActF32, R> k{};
                for (int t = 0; t < M; ++t) k.lens[t] = lens[t];
                k.m = (unsigned)M;
                k.gpt = (unsigned)((((lmax + 31) / 32 * 32) + WG * R - 1) / (WG * R));
                k.qs = 4096, k.ws = 32, k.ss = SS;
                return q.submit([&](sycl::handler &h) {
                    sycl::local_accessor<float, 1> lt(32 * 128 + 32, h);
                    h.parallel_for(sycl::nd_range<1>((size_t)M * k.gpt * WG, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                        k(it, dq, dk, dw, sb, &lt[0]);
                    });
                });
            };
            auto cmp = [&]() {
                std::vector<float> a(MT * SS), b(MT * SS);
                q.memcpy(a.data(), sa, a.size() * 4);
                q.memcpy(b.data(), sb, b.size() * 4).wait();
                for (int t = 0; t < M; ++t) {
                    const size_t n = (size_t)(lens[t] + 31) / 32 * 32;
                    if (std::memcmp(a.data() + t * SS, b.data() + t * SS, n * 4)) return false;
                }
                return true;
            };
            double tbm = 1e30, t2 = 1e30, t4 = 1e30, t8 = 1e30;
            bool same = true;
            q.fill(sa, 1.0f, MT * SS).wait();
            for (int r = 0; r < 8; ++r) { auto e = runBM(); e.wait(); tbm = std::min(tbm, us(e)); }
            q.fill(sb, 2.0f, MT * SS).wait();
            for (int r = 0; r < 8; ++r) { auto e = runR(std::integral_constant<int, 2>{}); e.wait(); t2 = std::min(t2, us(e)); }
            same = same && cmp();
            q.fill(sb, 2.0f, MT * SS).wait();
            for (int r = 0; r < 8; ++r) { auto e = runR(std::integral_constant<int, 4>{}); e.wait(); t4 = std::min(t4, us(e)); }
            same = same && cmp();
            q.fill(sb, 2.0f, MT * SS).wait();
            for (int r = 0; r < 8; ++r) { auto e = runR(std::integral_constant<int, 8>{}); e.wait(); t8 = std::min(t8, us(e)); }
            same = same && cmp();
            if (!same) ++bad;
            std::printf("%5d %7d %10.1f %10.1f %10.1f %10.1f  %s\n", M, len0, tbm, t2, t4, t8, same ? "identical" : "DIFFERENT");
        }
    }
    return bad ? 1 : 0;
}
