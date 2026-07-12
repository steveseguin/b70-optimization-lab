#include "mmvq.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <random>
#include <vector>

static double event_us(const sycl::event & event) {
    return double(event.get_profiling_info<sycl::info::event_profiling::command_end>() -
                  event.get_profiling_info<sycl::info::event_profiling::command_start>()) / 1000.0;
}

static double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

static int run(int k, int n, int iterations) {
    constexpr int m = 4;
    const int kb = k / 32;
    const size_t quant_bytes = size_t(k) * n / 2;
    const size_t weight_bytes = quant_bytes + size_t(kb) * n * sizeof(sycl::half);
    const int activation_stride = k + kb * sizeof(sycl::half2);

    std::mt19937 rng(0xb70);
    std::uniform_int_distribution<int> nibble(0, 15);
    std::uniform_int_distribution<int> q8(-127, 127);
    std::uniform_real_distribution<float> scale(0.0005f, 0.08f);
    std::vector<uint8_t> weights(weight_bytes);
    std::vector<int8_t> activations(size_t(m) * activation_stride);

    for (size_t i = 0; i < quant_bytes; ++i) {
        weights[i] = uint8_t(nibble(rng) | (nibble(rng) << 4));
    }
    auto * weight_scales = reinterpret_cast<sycl::half *>(weights.data() + quant_bytes);
    for (int row = 0; row < n; ++row) {
        for (int block = 0; block < kb; ++block) {
            weight_scales[size_t(row) * kb + block] = sycl::half(scale(rng));
        }
    }
    for (int row = 0; row < m; ++row) {
        int8_t * activation = activations.data() + size_t(row) * activation_stride;
        for (int i = 0; i < k; ++i) {
            activation[i] = int8_t(q8(rng));
        }
        auto * ds = reinterpret_cast<sycl::half2 *>(activation + k);
        for (int block = 0; block < kb; ++block) {
            ds[block] = sycl::half2(sycl::half(scale(rng)), sycl::half(scale(rng)));
        }
    }

    sycl::queue queue{sycl::gpu_selector_v, sycl::property_list{
        sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    auto * d_weights = sycl::malloc_device<uint8_t>(weight_bytes, queue);
    auto * d_activations = sycl::malloc_device<int8_t>(activations.size(), queue);
    auto * d_baseline = sycl::malloc_device<float>(size_t(m) * n, queue);
    auto * d_simd4 = sycl::malloc_device<float>(size_t(m) * n, queue);
    queue.memcpy(d_weights, weights.data(), weight_bytes);
    queue.memcpy(d_activations, activations.data(), activations.size()).wait();

    ggml_sycl_bench_reorder_q4_0_ncols(d_weights, d_activations, d_baseline,
        k, n, m, activation_stride, n, &queue, false).wait();
    ggml_sycl_bench_reorder_q4_0_ncols(d_weights, d_activations, d_simd4,
        k, n, m, activation_stride, n, &queue, true).wait();
    std::vector<float> baseline(size_t(m) * n), simd4(baseline.size());
    queue.memcpy(baseline.data(), d_baseline, baseline.size() * sizeof(float)).wait();
    queue.memcpy(simd4.data(), d_simd4, simd4.size() * sizeof(float)).wait();
    float max_abs = 0.0f;
    for (size_t i = 0; i < baseline.size(); ++i) {
        max_abs = std::max(max_abs, std::fabs(baseline[i] - simd4[i]));
    }

    std::vector<double> baseline_times, simd4_times;
    for (int i = 0; i < iterations; ++i) {
        sycl::event first;
        sycl::event second;
        if ((i & 1) == 0) {
            first = ggml_sycl_bench_reorder_q4_0_ncols(d_weights, d_activations, d_baseline,
                k, n, m, activation_stride, n, &queue, false);
            second = ggml_sycl_bench_reorder_q4_0_ncols(d_weights, d_activations, d_simd4,
                k, n, m, activation_stride, n, &queue, true);
        } else {
            second = ggml_sycl_bench_reorder_q4_0_ncols(d_weights, d_activations, d_simd4,
                k, n, m, activation_stride, n, &queue, true);
            first = ggml_sycl_bench_reorder_q4_0_ncols(d_weights, d_activations, d_baseline,
                k, n, m, activation_stride, n, &queue, false);
        }
        first.wait();
        second.wait();
        baseline_times.push_back(event_us(first));
        simd4_times.push_back(event_us(second));
    }

    const double baseline_us = median(baseline_times);
    const double simd4_us = median(simd4_times);
    std::cout << "M=4 K=" << k << " N=" << n << " max_abs=" << max_abs
              << " baseline_us=" << baseline_us << " simd4_us=" << simd4_us
              << " speedup=" << baseline_us / simd4_us << '\n';

    for (void * ptr : {static_cast<void *>(d_weights), static_cast<void *>(d_activations),
                       static_cast<void *>(d_baseline), static_cast<void *>(d_simd4)}) {
        sycl::free(ptr, queue);
    }
    return max_abs == 0.0f ? 0 : 2;
}

int main(int argc, char ** argv) {
    const int k = argc > 1 ? std::atoi(argv[1]) : 5120;
    const int n = argc > 2 ? std::atoi(argv[2]) : 5120;
    const int iterations = argc > 3 ? std::atoi(argv[3]) : 50;
    return run(k, n, iterations);
}
