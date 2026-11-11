// Does switching the register mode between launches cost time on a B70? (the step's 1.1 ms of gaps, ledger item 1)
// The engine builds with -ze-intel-enable-auto-large-GRF-mode, so the compiler picks 128 or 256 registers per kernel;
// in the decode step SparseSoftmaxPN runs in 256-register mode between 128-register kernels (38 per step, two mode
// changes each). A mode change may need the card to drain its pipeline. Chains of N launches on an in-order queue,
// timed by the host clock around the whole chain (no profiling) and by profiling events (span and kernel sum):
//   T128 / T256        a tiny dependent step (1 work-group of 32: y[i] = x[i] + 1) built for 128 / 256 registers
//   T128|T256 alt      the two alternating
//   T128|S32K alt      T128 alternating with the same step holding 32 KiB of local memory (128 registers)
//   G, G|T128, G|T256  a 5,120-column Q8_0 matrix-vector step (384 rows, ~2.1 MB, distinct copies) alone, and each
//                      followed by a tiny step of either mode (an engine-like sequence: big kernel, small kernel)
// Per form: us per launch (host clock / N), us per launch (profiling span / N), kernel us per launch, gap us.
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_grf_switch.cpp -o $S/bench_grf_switch
//   ONEAPI_DEVICE_SELECTOR=level_zero:N $S/bench_grf_switch
#include <sycl/sycl.hpp>
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;
namespace syclex = sycl::ext::oneapi::experimental;
namespace syclintel = sycl::ext::intel::experimental;

static constexpr unsigned C = 160, R = 384, NCOPY = 64;
static constexpr size_t RB = ((size_t)C * 34 + 15) & ~(size_t)15;

template <unsigned GRF> struct Tiny {
    const float *a;
    float *b;
    void operator()(sycl::nd_item<1> it) const {
        const size_t k = it.get_global_linear_id();
        b[k] = a[k] + 1.0f;
    }
    auto get(syclex::properties_tag) const {
        return syclex::properties{syclintel::grf_size<GRF>, syclex::sub_group_size<32>};
    }
};
struct TinySlm {
    const float *a;
    float *b;
    sycl::local_accessor<float, 1> lm;
    void operator()(sycl::nd_item<1> it) const {
        const size_t k = it.get_global_linear_id();
        lm[k] = a[k];
        sycl::group_barrier(it.get_group());
        b[k] = lm[k] + 1.0f;
    }
    auto get(syclex::properties_tag) const {
        return syclex::properties{syclintel::grf_size<128>, syclex::sub_group_size<32>};
    }
};

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
    // kinds: 0 T128, 1 T256, 2 TSLM, 3 G
    auto one = [&](sycl::queue &q, int kind, int i) -> sycl::event {
        float *a = (i & 1) ? y : x, *b = (i & 1) ? x : y;
        switch (kind) {
        case 0: return q.parallel_for(sycl::nd_range<1>(32, 32), Tiny<128>{a, b});
        case 1: return q.parallel_for(sycl::nd_range<1>(32, 32), Tiny<256>{a, b});
        case 2:
            return q.submit([&](sycl::handler &h) {
                sycl::local_accessor<float, 1> lm(8192, h);
                h.parallel_for(sycl::nd_range<1>(32, 32), TinySlm{a, b, lm});
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
    struct Form {
        const char *name;
        int k0, k1; // launch i uses k0 when i is even, k1 when odd
    };
    const Form forms[] = {{"T128", 0, 0},         {"T256", 1, 1},         {"T128|T256 alt", 0, 1},
                          {"T128|S32K alt", 0, 2}, {"G", 3, 3},            {"G|T128", 3, 0},
                          {"G|T256", 3, 1}};
    std::printf("%-16s %14s %14s %14s %14s\n", "form", "host us/launch", "span us/launch", "kernel us", "gap us");
    for (const Form &f : forms) {
        std::vector<double> th, ts, tk;
        for (int rep = 0; rep < 9; ++rep) {
            qn.wait();
            const auto t0 = std::chrono::steady_clock::now();
            for (int i = 0; i < N; ++i) one(qn, (i & 1) ? f.k1 : f.k0, i);
            qn.wait();
            const auto t1 = std::chrono::steady_clock::now();
            std::vector<sycl::event> ev;
            for (int i = 0; i < N; ++i) ev.push_back(one(qp, (i & 1) ? f.k1 : f.k0, i));
            qp.wait();
            double ksum = 0;
            for (auto &e : ev)
                ksum += (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                         e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
            const double span = (ev.back().get_profiling_info<sycl::info::event_profiling::command_end>() -
                                 ev.front().get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
            if (rep < 2) continue; // warm-up
            th.push_back(std::chrono::duration<double, std::micro>(t1 - t0).count() / N);
            ts.push_back(span / N);
            tk.push_back(ksum / N);
        }
        auto med = [](std::vector<double> v) { std::sort(v.begin(), v.end()); return v[v.size() / 2]; };
        std::printf("%-16s %14.2f %14.2f %14.2f %14.2f\n", f.name, med(th), med(ts), med(tk), med(ts) - med(tk));
        std::fflush(stdout);
    }
    return 0;
}
