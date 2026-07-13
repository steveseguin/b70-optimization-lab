#include "q27_xe2_module.h"

#include <sycl/sycl.hpp>

#include <dlfcn.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef Q27_XE2_TOOLCHAIN_ABI
#define Q27_XE2_TOOLCHAIN_ABI "oneapi-2026.0-sycl-cxx17"
#endif

namespace {

class direct_smoke_axpy_kernel;

using clock_type = std::chrono::steady_clock;

double milliseconds(clock_type::time_point begin, clock_type::time_point end) {
    return std::chrono::duration<double, std::milli>(end - begin).count();
}

void direct_launch(sycl::queue &queue, const float *input, float *output, size_t count, float alpha) {
    queue.submit([&](sycl::handler &handler) {
        handler.parallel_for<direct_smoke_axpy_kernel>(sycl::range<1>(count), [=](sycl::id<1> index) {
            output[index] += alpha * input[index];
        });
    });
}

} // namespace

int main(int argc, char **argv) try {
    if (argc != 2) {
        std::cerr << "usage: " << argv[0] << " MODULE.so\n";
        return 2;
    }

    const auto load_begin = clock_type::now();
    void *handle = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (handle == nullptr) {
        throw std::runtime_error(dlerror());
    }
    auto getter = reinterpret_cast<q27_xe2_get_module_v1_fn>(dlsym(handle, Q27_XE2_GETTER_SYMBOL));
    if (getter == nullptr) {
        throw std::runtime_error(dlerror());
    }
    const q27_xe2_module_v1 *module = getter();
    const auto load_end = clock_type::now();

    if (module == nullptr || module->abi_magic != Q27_XE2_ABI_MAGIC ||
        module->abi_version != Q27_XE2_ABI_VERSION ||
        module->struct_size < sizeof(q27_xe2_module_v1) ||
        module->launch == nullptr || module->query_workspace == nullptr) {
        throw std::runtime_error("module ABI validation failed");
    }
    if (module->toolchain_abi == nullptr || std::strcmp(module->toolchain_abi, Q27_XE2_TOOLCHAIN_ABI) != 0) {
        throw std::runtime_error("module toolchain ABI does not match host");
    }

    sycl::queue queue{sycl::gpu_selector_v, sycl::property::queue::in_order{}};
    constexpr size_t count = 4096;
    constexpr int warmups = 32;
    constexpr int iterations = 2000;
    constexpr float alpha = 0.25f;

    float *input = sycl::malloc_device<float>(count, queue);
    float *output = sycl::malloc_device<float>(count, queue);
    if (input == nullptr || output == nullptr) {
        throw std::runtime_error("device allocation failed");
    }
    std::vector<float> host_input(count, 2.0f);
    std::vector<float> host_output(count, 1.0f);
    queue.memcpy(input, host_input.data(), count * sizeof(float));
    queue.memcpy(output, host_output.data(), count * sizeof(float));
    queue.wait_and_throw();

    q27_xe2_launch_v1 launch{};
    launch.struct_size = sizeof(launch);
    launch.op = Q27_XE2_OP_SMOKE_AXPY;
    launch.flags = Q27_XE2_QUEUE_IS_IN_ORDER;
    launch.queue = &queue;
    launch.input0 = input;
    launch.output0 = output;
    launch.cols = count;
    launch.scalar0 = alpha;

    q27_xe2_workspace_v1 workspace{};
    if (module->query_workspace(launch.op, 1, launch.cols, &workspace) != Q27_XE2_OK || workspace.bytes != 0) {
        throw std::runtime_error("workspace query failed");
    }

    for (int i = 0; i < warmups; ++i) {
        if (module->launch(&launch) != Q27_XE2_OK) {
            throw std::runtime_error("module warmup launch failed");
        }
    }
    queue.wait_and_throw();

    queue.memset(output, 0, count * sizeof(float)).wait();
    const auto direct_begin = clock_type::now();
    for (int i = 0; i < iterations; ++i) {
        direct_launch(queue, input, output, count, alpha);
    }
    queue.wait_and_throw();
    const auto direct_end = clock_type::now();

    queue.memset(output, 0, count * sizeof(float)).wait();
    const auto module_begin = clock_type::now();
    for (int i = 0; i < iterations; ++i) {
        const int32_t status = module->launch(&launch);
        if (status != Q27_XE2_OK) {
            throw std::runtime_error("module timed launch failed with status " + std::to_string(status));
        }
    }
    queue.wait_and_throw();
    const auto module_end = clock_type::now();

    queue.memcpy(host_output.data(), output, count * sizeof(float)).wait();
    const float expected = iterations * alpha * 2.0f;
    const bool correct = std::all_of(host_output.begin(), host_output.end(), [&](float value) {
        return std::abs(value - expected) < 0.01f;
    });

    const double direct_ms = milliseconds(direct_begin, direct_end) / iterations;
    const double module_ms = milliseconds(module_begin, module_end) / iterations;
    const double overhead_ms = module_ms - direct_ms;
    const bool overhead_gate = overhead_ms < 0.1;

    std::cout << std::fixed << std::setprecision(6)
              << "{\n"
              << "  \"module\": \"" << module->module_name << "\",\n"
              << "  \"build_id\": \"" << module->module_build_id << "\",\n"
              << "  \"target_arch\": \"" << module->target_arch << "\",\n"
              << "  \"device\": \"" << queue.get_device().get_info<sycl::info::device::name>() << "\",\n"
              << "  \"dlopen_ms\": " << milliseconds(load_begin, load_end) << ",\n"
              << "  \"iterations\": " << iterations << ",\n"
              << "  \"direct_wall_ms_per_call\": " << direct_ms << ",\n"
              << "  \"module_wall_ms_per_call\": " << module_ms << ",\n"
              << "  \"module_overhead_ms_per_call\": " << overhead_ms << ",\n"
              << "  \"correct\": " << (correct ? "true" : "false") << ",\n"
              << "  \"overhead_lt_0_1ms\": " << (overhead_gate ? "true" : "false") << "\n"
              << "}\n";

    sycl::free(input, queue);
    sycl::free(output, queue);
    queue.wait_and_throw();
    dlclose(handle);
    return correct && overhead_gate ? 0 : 1;
} catch (const std::exception &error) {
    std::cerr << "hot-kernel-module error: " << error.what() << '\n';
    return 1;
}
