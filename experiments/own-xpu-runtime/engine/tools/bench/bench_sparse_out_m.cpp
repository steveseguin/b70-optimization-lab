// The attention output for blocks of M tokens (prompt reading: M = 16; checks of guesses: 2-6): OutM<SparseOutJB<512,
// 1, 16>> against OutMC<SparseOutJC<512, 16, CH>> (sycl_v41.hpp), M = 1..16, 640-slot lists per token, 16 / 12 / 8
// heads. In the engine (g76, tp76) prompt reading on the 69K document was 1.3 % slower with OutMC at M = 16, the
// one-token answers 3.0 % faster. One card, GPU time per launch; out and ry compared BITWISE.
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_sparse_out_m.cpp -o bench_sparse_out_m
//   ONEAPI_DEVICE_SELECTOR=level_zero:1 ./bench_sparse_out_m
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    constexpr unsigned HD = 512, W = 144, CROWS = 24000, MAXH = 16, MAXI = 640, MAXM = 16;
    uint16_t *kvw = sycl::malloc_device<uint16_t>((size_t)W * HD, q), *kvc = sycl::malloc_device<uint16_t>((size_t)CROWS * HD, q);
    int32_t *ix = sycl::malloc_device<int32_t>((size_t)MAXM * MAXI, q);
    float *wt = sycl::malloc_device<float>((size_t)MAXM * MAXH * MAXI, q), *cs = sycl::malloc_device<float>((size_t)MAXM * 64, q);
    float *ob[3], *yb[3];
    for (int f = 0; f < 3; ++f) {
        ob[f] = sycl::malloc_device<float>((size_t)MAXM * MAXH * HD, q);
        yb[f] = sycl::malloc_device<float>((size_t)MAXM * MAXH * HD, q);
    }
    std::mt19937 rng(17);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::uniform_int_distribution<int> ue(-12, 8);
    auto bf = [](float f) { uint32_t u; std::memcpy(&u, &f, 4); return (uint16_t)(u >> 16); };
    {
        std::vector<uint16_t> hw((size_t)W * HD), hc((size_t)CROWS * HD);
        for (auto &v : hw) v = bf(nd(rng) * std::ldexp(1.0f, ue(rng)));
        for (auto &v : hc) v = bf(nd(rng) * std::ldexp(1.0f, ue(rng)));
        q.memcpy(kvw, hw.data(), hw.size() * 2);
        q.memcpy(kvc, hc.data(), hc.size() * 2).wait();
        std::vector<float> hcs((size_t)MAXM * 64);
        for (auto &v : hcs) v = nd(rng);
        q.memcpy(cs, hcs.data(), hcs.size() * 4).wait();
        // lists: per token the window (rows 0..127 + the block's rows up to the token) and 512 compressed rows
        std::vector<int32_t> hi((size_t)MAXM * MAXI);
        for (unsigned t = 0; t < MAXM; ++t) {
            for (int i = 0; i < 128; ++i) hi[t * MAXI + i] = i + (int)t <= 143 ? i + (int)t : -1;
            std::vector<int> rows(CROWS);
            for (int r = 0; r < (int)CROWS; ++r) rows[r] = r;
            std::shuffle(rows.begin(), rows.end(), rng);
            std::sort(rows.begin(), rows.begin() + 512);
            for (int i = 0; i < 512; ++i) hi[t * MAXI + 128 + i] = (int)W + rows[i];
        }
        q.memcpy(ix, hi.data(), hi.size() * 4);
        std::vector<float> hw2((size_t)MAXM * MAXH * MAXI);
        for (auto &v : hw2) v = std::exp(2.0f * nd(rng)) * 1e-3f;
        q.memcpy(wt, hw2.data(), hw2.size() * 4).wait();
    }
    auto run = [&](int f, unsigned M, int heads, int n) -> sycl::event {
        const size_t is = MAXI, ws = (size_t)MAXH * MAXI, os = (size_t)MAXH * HD;
        if (f == 0) {
            SparseOutJB<HD, 1, 16> so{n, heads, (int)W};
            so.ry = yb[0];
            so.cosb = cs;
            so.sinb = cs + 32;
            const unsigned gpo = (unsigned)(heads * HD / 64);
            OutM<SparseOutJB<HD, 1, 16>> k{so, gpo, M, is, ws, os, os};
            // (the rope tables move 32 per token in OutM: the bench's tables are 64 per token, sin = cos + 32 ... the
            // same pointers for both forms, which is all the comparison needs)
            return q.parallel_for(sycl::nd_range<1>((size_t)M * gpo * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k(it, (const uint16_t *)kvw, (const uint16_t *)kvc, (const int32_t *)ix, (const float *)wt, ob[0]);
            });
        }
        auto mc = [&](auto so, int fi) {
            using SC = decltype(so);
            so.ry = yb[fi];
            so.cosb = cs;
            so.sinb = cs + 32;
            const unsigned gpo = (unsigned)SC::groups(heads);
            OutMC<SC> k{so, gpo, M, is, ws, os, os};
            float *o = ob[fi];
            return q.submit([&](sycl::handler &h) {
                sycl::local_accessor<uint32_t, 1> lt(SC::SLM, h);
                h.parallel_for(sycl::nd_range<1>((size_t)M * gpo * SC::WG, SC::WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                    k(it, (const uint16_t *)kvw, (const uint16_t *)kvc, (const int32_t *)ix, (const float *)wt, o, &lt[0]);
                });
            });
        };
        if (f == 1) return mc(SparseOutJC<HD, 16, 128>{n, heads, (int)W}, 1);
        return mc(SparseOutJC<HD, 16, 64>{n, heads, (int)W}, 2);
    };
    for (int r = 0; r < 300; ++r) run(r % 3, 16, 16, 640);
    q.wait();
    long bad = 0;
    std::printf("%5s %3s | %16s | %16s | %16s\n", "heads", "M", "OutM<JB> us", "OutMC<JC128> us", "OutMC<JC64> us");
    for (int heads : {16, 12, 8})
        for (unsigned M : {1u, 2u, 3u, 4u, 5u, 6u, 8u, 12u, 16u}) {
            for (int f = 0; f < 3; ++f) {
                q.fill(ob[f], -7.0f, (size_t)MAXM * MAXH * HD);
                q.fill(yb[f], -7.0f, (size_t)MAXM * MAXH * HD);
            }
            q.wait();
            std::vector<double> t[3];
            for (int r = 0; r <= 40; ++r)
                for (int f = 0; f < 3; ++f) {
                    auto e = run(f, M, heads, 640);
                    e.wait();
                    if (r) t[f].push_back(ev_us(e));
                }
            const size_t nn = (size_t)MAXM * MAXH * HD;
            std::vector<float> r0(nn), y0(nn), x(nn), y(nn);
            q.memcpy(r0.data(), ob[0], nn * 4);
            q.memcpy(y0.data(), yb[0], nn * 4).wait();
            bool same[3] = {true, true, true};
            for (int f = 1; f < 3; ++f) {
                q.memcpy(x.data(), ob[f], nn * 4);
                q.memcpy(y.data(), yb[f], nn * 4).wait();
                same[f] = !std::memcmp(x.data(), r0.data(), nn * 4) && !std::memcmp(y.data(), y0.data(), nn * 4);
                bad += !same[f];
            }
            for (auto &v : t) std::sort(v.begin(), v.end());
            std::printf("%5d %3u | %16.1f | %14.1f %s | %14.1f %s\n", heads, M, t[0][t[0].size() / 2], t[1][t[1].size() / 2],
                        same[1] ? "y" : "NO", t[2][t[2].size() / 2], same[2] ? "y" : "NO");
        }
    std::printf("(median us per launch; y = out and ry bitwise = OutM<JB>)\n");
    std::printf(bad ? "FAIL (%ld differ)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
