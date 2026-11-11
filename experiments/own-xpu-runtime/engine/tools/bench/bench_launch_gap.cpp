// What does one launch cost on a B70, without the profiler's timestamps? (strategy method step 1 / external idea #0)
// Chains of N launches on an in-order queue, timed by the host clock around the whole chain (queue without
// profiling) and, separately, with profiling events (first start to last end). Forms:
//   E1  empty kernel, 1 work-group of 32          E512  empty kernel, 512 work-groups of 512 (a full card)
//   T   a tiny dependent step: 1 work-group of 32 reads x[i] and writes y[i] = x[i] + 1 (the next launch reads y)
//   G   a 5,120-column Q8_0 matrix-vector step of 384 rows (GemvQ8P<160>, ~2.1 MB, about a shared-expert slice),
//       each launch reading the previous launch's output (rows of distinct weights, 64 copies so the cache misses)
// Per form: us per launch (host clock / N, no profiling), us per launch (profiling span / N), and for G the sum of
// the kernels' own durations / N (so the gap = span - kernels).
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_launch_gap.cpp -o $S/bench_launch_gap
//   ONEAPI_DEVICE_SELECTOR=level_zero:N $S/bench_launch_gap
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

static constexpr unsigned C = 160, R = 384, NCOPY = 64;
static constexpr size_t RB = ((size_t)C * 34 + 15) & ~(size_t)15;

int main() {
    sycl::queue qp{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    sycl::queue qn{qp.get_context(), qp.get_device(), {sycl::property::queue::in_order{}}};
    std::printf("%s\n", qp.get_device().get_info<sycl::info::device::name>().c_str());
    std::mt19937 rng(3);
    std::uniform_int_distribution<int> ub(0, 255);
    std::vector<uint8_t> hw((size_t)NCOPY * R * RB);
    for (size_t r = 0; r < (size_t)NCOPY * R; ++r) {
        uint8_t *row = &hw[r * RB];
        for (unsigned i = 0; i < C * 32; ++i) row[i] = (uint8_t)ub(rng);
        uint16_t *dp = reinterpret_cast<uint16_t *>(row + C * 32);
        for (unsigned i = 0; i < C; ++i) dp[i] = (uint16_t)(0x1000 + (ub(rng) & 0x3ff));
    }
    uint8_t *w = sycl::malloc_device<uint8_t>(hw.size(), qp);
    float *x = sycl::malloc_device<float>(8192, qp), *y = sycl::malloc_device<float>(8192, qp);
    qp.memcpy(w, hw.data(), hw.size());
    qp.fill(x, 0.5f, 8192);
    qp.fill(y, 0.5f, 8192).wait();
    constexpr int N = 400;
    auto launch = [&](sycl::queue &q, int form, int i) -> sycl::event {
        float *a = (i & 1) ? y : x, *b = (i & 1) ? x : y;
        switch (form) {
        case 0: return q.parallel_for(sycl::nd_range<1>(32, 32), [=](sycl::nd_item<1>) [[sycl::reqd_sub_group_size(32)]] {});
        case 1: return q.parallel_for(sycl::nd_range<1>(512 * 512, 512), [=](sycl::nd_item<1>) [[sycl::reqd_sub_group_size(32)]] {});
        case 2:
            return q.parallel_for(sycl::nd_range<1>(32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                const size_t k = it.get_global_linear_id();
                b[k] = a[k] + 1.0f;
            });
        default: {
            const uint8_t *wk = w + (size_t)(i % NCOPY) * R * RB;
            const GemvQ8P<C, ActF32> k{R, 0};
            return q.parallel_for(sycl::nd_range<1>((R / 16) * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k(it, wk, a, b);
            });
        }
        }
    };
    const char *names[4] = {"E1 empty, 1 x 32", "E512 empty, 512 x 512", "T tiny dependent, 1 x 32", "G Q8_0 384 x 5120 rows"};
    std::printf("%-26s %14s %14s %14s %14s\n", "form", "host us/launch", "span us/launch", "kernel us", "gap us");
    for (int form = 0; form < 4; ++form) {
        std::vector<double> th, ts, tk;
        for (int rep = 0; rep < 7; ++rep) {
            qn.wait();
            const auto t0 = std::chrono::steady_clock::now();
            for (int i = 0; i < N; ++i) launch(qn, form, i);
            qn.wait();
            const auto t1 = std::chrono::steady_clock::now();
            std::vector<sycl::event> ev;
            for (int i = 0; i < N; ++i) ev.push_back(launch(qp, form, i));
            qp.wait();
            double ksum = 0;
            for (auto &e : ev)
                ksum += (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                         e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
            const double span = (ev.back().get_profiling_info<sycl::info::event_profiling::command_end>() -
                                 ev.front().get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
            if (rep == 0) continue;
            th.push_back(std::chrono::duration<double, std::micro>(t1 - t0).count() / N);
            ts.push_back(span / N);
            tk.push_back(ksum / N);
        }
        auto med = [](std::vector<double> v) { std::sort(v.begin(), v.end()); return v[v.size() / 2]; };
        std::printf("%-26s %14.2f %14.2f %14.2f %14.2f\n", names[form], med(th), med(ts), med(tk), med(ts) - med(tk));
    }
    return 0;
}
