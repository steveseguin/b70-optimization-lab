#include <sycl/sycl.hpp>
#include <oneapi/dnnl/dnnl.hpp>
#include <oneapi/dnnl/dnnl_sycl.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using bf16 = sycl::ext::oneapi::bfloat16;

namespace {

uint32_t xorshift32(uint32_t & state) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return state;
}

float signed_unit(uint32_t & state) {
    return float(int(xorshift32(state) & 0xffffu) - 32768) / 32768.0f;
}

uint32_t bits(float value) {
    uint32_t result;
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

uint64_t output_hash(const std::vector<float> & values) {
    uint64_t hash = 1469598103934665603ull;
    for (const float value : values) {
        const uint32_t word = bits(value);
        for (int shift = 0; shift < 32; shift += 8) {
            hash ^= (word >> shift) & 0xffu;
            hash *= 1099511628211ull;
        }
    }
    return hash;
}

template <typename Submit>
double batch_time_ms(sycl::queue & queue, int iterations, Submit && submit) {
    const auto start = std::chrono::steady_clock::now();
    for (int i = 0; i < iterations; ++i) {
        submit();
    }
    queue.wait_and_throw();
    const auto end = std::chrono::steady_clock::now();
    return std::chrono::duration<double, std::milli>(end - start).count() / iterations;
}

struct MatmulPath {
    dnnl::matmul primitive;
    std::unordered_map<int, dnnl::memory> args;
    void * scratch = nullptr;
};

MatmulPath make_path(
        const dnnl::engine & engine,
        void * src,
        const dnnl::memory::desc & src_md,
        void * weights,
        const dnnl::memory::desc & weights_md,
        void * dst,
        const dnnl::memory::desc & dst_md,
        sycl::queue & queue) {
    dnnl::primitive_attr attr;
    attr.set_scratchpad_mode(dnnl::scratchpad_mode::user);
    auto pd = dnnl::matmul::primitive_desc(engine, src_md, weights_md, dst_md, attr);
    void * scratch = nullptr;
    if (pd.scratchpad_desc().get_size() != 0) {
        scratch = sycl::malloc_device<uint8_t>(pd.scratchpad_desc().get_size(), queue);
        if (!scratch) {
            throw std::runtime_error("scratchpad allocation failed");
        }
    }
    return {
        dnnl::matmul(pd),
        {
            {DNNL_ARG_SRC, dnnl::memory(src_md, engine, src)},
            {DNNL_ARG_WEIGHTS, dnnl::memory(weights_md, engine, weights)},
            {DNNL_ARG_DST, dnnl::memory(pd.dst_desc(), engine, dst)},
            {DNNL_ARG_SCRATCHPAD, dnnl::memory(pd.scratchpad_desc(), engine, scratch)},
        },
        scratch,
    };
}

} // namespace

int main(int argc, char ** argv) {
    const int m = argc > 1 ? std::stoi(argv[1]) : 4992;
    const int n = argc > 2 ? std::stoi(argv[2]) : 16;
    const int k = argc > 3 ? std::stoi(argv[3]) : 6656;
    const int iterations = argc > 4 ? std::stoi(argv[4]) : 200;
    const int warmups = 12;
    if (m <= 0 || n <= 0 || k <= 0 || iterations <= 0) {
        throw std::invalid_argument("M, N, K, and iterations must be positive");
    }

    sycl::queue queue(sycl::gpu_selector_v,
        sycl::property_list{sycl::property::queue::in_order{}});
    std::cout << "device=" << queue.get_device().get_info<sycl::info::device::name>()
              << " shape=" << m << "x" << n << "x" << k
              << " iterations=" << iterations << '\n';

    uint32_t rng = 0x4d555345u;
    std::vector<bf16> host_weight(size_t(m) * k);
    std::vector<bf16> host_activation(size_t(n) * k);
    for (auto & value : host_weight) {
        value = bf16(signed_unit(rng) * 0.03125f);
    }
    for (auto & value : host_activation) {
        value = bf16(signed_unit(rng) * 0.125f);
    }

    auto * weight = sycl::malloc_device<bf16>(host_weight.size(), queue);
    auto * activation = sycl::malloc_device<bf16>(host_activation.size(), queue);
    auto * out_incumbent = sycl::malloc_device<float>(size_t(m) * n, queue);
    auto * out_transposed = sycl::malloc_device<float>(size_t(m) * n, queue);
    auto * out_incumbent_2d = sycl::malloc_device<float>(size_t(m) * n, queue);
    auto * out_transposed_2d = sycl::malloc_device<float>(size_t(m) * n, queue);
    if (!weight || !activation || !out_incumbent || !out_transposed ||
            !out_incumbent_2d || !out_transposed_2d) {
        throw std::runtime_error("USM allocation failed");
    }
    queue.copy(host_weight.data(), weight, host_weight.size());
    queue.copy(host_activation.data(), activation, host_activation.size());
    queue.wait_and_throw();

    const auto engine = dnnl::sycl_interop::make_engine(
        queue.get_device(), queue.get_context());
    const auto stream = dnnl::sycl_interop::make_stream(engine, queue);
    using dt = dnnl::memory::data_type;

    const auto incumbent_src_md = dnnl::memory::desc(
        {1, m, k}, dt::bf16, {int64_t(m) * k, k, 1});
    const auto incumbent_weights_md = dnnl::memory::desc(
        {1, k, n}, dt::bf16, {int64_t(k) * n, 1, k});
    const auto incumbent_dst_md = dnnl::memory::desc(
        {1, m, n}, dt::f32, {int64_t(m) * n, 1, m});
    auto incumbent = make_path(engine,
        weight, incumbent_src_md,
        activation, incumbent_weights_md,
        out_incumbent, incumbent_dst_md, queue);

    const auto transposed_src_md = dnnl::memory::desc(
        {1, n, k}, dt::bf16, {int64_t(n) * k, k, 1});
    const auto transposed_weights_md = dnnl::memory::desc(
        {1, k, m}, dt::bf16, {int64_t(k) * m, 1, k});
    const auto transposed_dst_md = dnnl::memory::desc(
        {1, n, m}, dt::f32, {int64_t(n) * m, m, 1});
    auto transposed = make_path(engine,
        activation, transposed_src_md,
        weight, transposed_weights_md,
        out_transposed, transposed_dst_md, queue);

    const auto incumbent_2d_src_md = dnnl::memory::desc(
        {m, k}, dt::bf16, {k, 1});
    const auto incumbent_2d_weights_md = dnnl::memory::desc(
        {k, n}, dt::bf16, {1, k});
    const auto incumbent_2d_dst_md = dnnl::memory::desc(
        {m, n}, dt::f32, {1, m});
    auto incumbent_2d = make_path(engine,
        weight, incumbent_2d_src_md,
        activation, incumbent_2d_weights_md,
        out_incumbent_2d, incumbent_2d_dst_md, queue);

    const auto transposed_2d_src_md = dnnl::memory::desc(
        {n, k}, dt::bf16, {k, 1});
    const auto transposed_2d_weights_md = dnnl::memory::desc(
        {k, m}, dt::bf16, {1, k});
    const auto transposed_2d_dst_md = dnnl::memory::desc(
        {n, m}, dt::f32, {m, 1});
    auto transposed_2d = make_path(engine,
        activation, transposed_2d_src_md,
        weight, transposed_2d_weights_md,
        out_transposed_2d, transposed_2d_dst_md, queue);

    auto submit_incumbent = [&] { incumbent.primitive.execute(stream, incumbent.args); };
    auto submit_transposed = [&] { transposed.primitive.execute(stream, transposed.args); };
    auto submit_incumbent_2d = [&] { incumbent_2d.primitive.execute(stream, incumbent_2d.args); };
    auto submit_transposed_2d = [&] { transposed_2d.primitive.execute(stream, transposed_2d.args); };
    for (int i = 0; i < warmups; ++i) {
        submit_incumbent();
        submit_transposed();
        submit_incumbent_2d();
        submit_transposed_2d();
    }
    queue.wait_and_throw();

    submit_incumbent();
    submit_transposed();
    submit_incumbent_2d();
    submit_transposed_2d();
    queue.wait_and_throw();
    std::vector<float> host_incumbent(size_t(m) * n);
    std::vector<float> host_transposed(size_t(m) * n);
    std::vector<float> host_incumbent_2d(size_t(m) * n);
    std::vector<float> host_transposed_2d(size_t(m) * n);
    queue.copy(out_incumbent, host_incumbent.data(), host_incumbent.size());
    queue.copy(out_transposed, host_transposed.data(), host_transposed.size());
    queue.copy(out_incumbent_2d, host_incumbent_2d.data(), host_incumbent_2d.size());
    queue.copy(out_transposed_2d, host_transposed_2d.data(), host_transposed_2d.size());
    queue.wait_and_throw();

    size_t mismatches = 0;
    size_t incumbent_2d_mismatches = 0;
    size_t transposed_2d_mismatches = 0;
    float max_abs_error = 0.0f;
    size_t first_mismatch = host_incumbent.size();
    for (size_t i = 0; i < host_incumbent.size(); ++i) {
        if (bits(host_incumbent[i]) != bits(host_transposed[i])) {
            ++mismatches;
            first_mismatch = std::min(first_mismatch, i);
            max_abs_error = std::max(max_abs_error,
                std::abs(host_incumbent[i] - host_transposed[i]));
        }
        incumbent_2d_mismatches += bits(host_incumbent[i]) != bits(host_incumbent_2d[i]);
        transposed_2d_mismatches += bits(host_incumbent[i]) != bits(host_transposed_2d[i]);
    }

    // Use A/B/A ordering to expose drift or cache-state bias in the short screen.
    const double incumbent_before_ms = batch_time_ms(queue, iterations, submit_incumbent);
    const double transposed_ms = batch_time_ms(queue, iterations, submit_transposed);
    const double incumbent_2d_ms = batch_time_ms(queue, iterations, submit_incumbent_2d);
    const double transposed_2d_ms = batch_time_ms(queue, iterations, submit_transposed_2d);
    const double incumbent_after_ms = batch_time_ms(queue, iterations, submit_incumbent);
    const double incumbent_ms = 0.5 * (incumbent_before_ms + incumbent_after_ms);
    std::cout << std::fixed << std::setprecision(6)
              << "incumbent_before_ms=" << incumbent_before_ms
              << " transposed_ms=" << transposed_ms
              << " incumbent_2d_ms=" << incumbent_2d_ms
              << " transposed_2d_ms=" << transposed_2d_ms
              << " incumbent_after_ms=" << incumbent_after_ms
              << " pooled_incumbent_ms=" << incumbent_ms
              << " transposed_over_incumbent=" << (transposed_ms / incumbent_ms)
              << " mismatches=" << mismatches
              << " incumbent_2d_mismatches=" << incumbent_2d_mismatches
              << " transposed_2d_mismatches=" << transposed_2d_mismatches
              << " max_abs_error=" << max_abs_error
              << " incumbent_hash=0x" << std::hex << output_hash(host_incumbent)
              << std::dec << '\n';
    if (first_mismatch != host_incumbent.size()) {
        std::cout << "first_mismatch=" << first_mismatch
                  << " incumbent=0x" << std::hex << bits(host_incumbent[first_mismatch])
                  << " transposed=0x" << bits(host_transposed[first_mismatch]) << std::dec
                  << " incumbent_value=" << host_incumbent[first_mismatch]
                  << " transposed_value=" << host_transposed[first_mismatch] << '\n';
    }

    sycl::free(transposed_2d.scratch, queue);
    sycl::free(incumbent_2d.scratch, queue);
    sycl::free(transposed.scratch, queue);
    sycl::free(incumbent.scratch, queue);
    sycl::free(out_transposed_2d, queue);
    sycl::free(out_incumbent_2d, queue);
    sycl::free(out_transposed, queue);
    sycl::free(out_incumbent, queue);
    sycl::free(activation, queue);
    sycl::free(weight, queue);

    const bool exact = mismatches == 0 && incumbent_2d_mismatches == 0 &&
        transposed_2d_mismatches == 0;
    std::cout << "exact_gate=" << (exact ? "PASS" : "FAIL") << '\n';
    return exact ? 0 : 2;
}
