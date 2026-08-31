#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <unordered_map>
#include <vector>

#include <sycl/sycl.hpp>
#include <oneapi/dnnl/dnnl.hpp>
#include <oneapi/dnnl/dnnl_sycl.hpp>

// Mechanism-only benchmark for the c96 Qwen3.8-27B oneDNN wrapper. It compares
// reconstructing the primitive plan on every invocation with reusing only the
// pointer-independent plan. Pointer-bound memory objects and the argument map
// are deliberately rebuilt in both arms because graph tensor addresses vary.

namespace {

using clock_type = std::chrono::steady_clock;
using dt = dnnl::memory::data_type;

constexpr int64_t m = 8704;
constexpr int64_t n = 96;
constexpr int64_t k = 5120;

struct Plan {
    dnnl::memory::desc a_md;
    dnnl::memory::desc b_md;
    dnnl::memory::desc c_md;
    dnnl::memory::desc scratchpad_md;
    dnnl::matmul::primitive_desc pd;
    dnnl::matmul primitive;

    explicit Plan(const dnnl::engine & engine)
        : a_md({1, m, k}, dt::f16, {m * k, k, 1}),
          b_md({1, k, n}, dt::f16, {k * n, 1, k}),
          c_md({1, m, n}, dt::f32, {m * n, 1, m}),
          pd(make_pd(engine, a_md, b_md, c_md)),
          primitive(pd) {
        scratchpad_md = pd.scratchpad_desc();
    }

private:
    static dnnl::matmul::primitive_desc make_pd(
        const dnnl::engine & engine,
        const dnnl::memory::desc & a,
        const dnnl::memory::desc & b,
        const dnnl::memory::desc & c) {
        dnnl::primitive_attr attr;
        attr.set_scratchpad_mode(dnnl::scratchpad_mode::user);
        attr.set_fpmath_mode(dnnl::fpmath_mode::f16);
        attr.set_deterministic(true);
        return dnnl::matmul::primitive_desc(engine, a, b, c, attr);
    }
};

void execute_plan(const Plan & plan, const dnnl::engine & engine,
                  dnnl::stream & stream, void * a_ptr, void * b_ptr,
                  void * c_ptr, void * scratchpad_ptr) {
    auto a_mem = dnnl::memory(plan.a_md, engine, a_ptr);
    auto b_mem = dnnl::memory(plan.b_md, engine, b_ptr);
    auto c_mem = dnnl::memory(plan.pd.dst_desc(), engine, c_ptr);
    auto scratchpad_mem = dnnl::memory(plan.scratchpad_md, engine, scratchpad_ptr);
    std::unordered_map<int, dnnl::memory> args;
    args.insert({DNNL_ARG_SRC, a_mem});
    args.insert({DNNL_ARG_WEIGHTS, b_mem});
    args.insert({DNNL_ARG_DST, c_mem});
    args.insert({DNNL_ARG_SCRATCHPAD, scratchpad_mem});
    plan.primitive.execute(stream, args);
}

double percentile(std::vector<double> values, double q) {
    std::sort(values.begin(), values.end());
    const double pos = q * static_cast<double>(values.size() - 1);
    const size_t lo = static_cast<size_t>(std::floor(pos));
    const size_t hi = static_cast<size_t>(std::ceil(pos));
    const double frac = pos - static_cast<double>(lo);
    return values[lo] * (1.0 - frac) + values[hi] * frac;
}

template <typename Fn>
double timed_per_invocation_ms(Fn && fn, int invocations) {
    const auto start = clock_type::now();
    fn();
    const auto elapsed = std::chrono::duration<double, std::milli>(
        clock_type::now() - start).count();
    return elapsed / static_cast<double>(invocations);
}

} // namespace

int main(int argc, char ** argv) {
    try {
        const int warmup = argc > 1 ? std::stoi(argv[1]) : 8;
        const int blocks = argc > 2 ? std::stoi(argv[2]) : 6;
        const int samples_per_block = argc > 3 ? std::stoi(argv[3]) : 20;
        const int invocations = argc > 4 ? std::stoi(argv[4]) : 8;
        if (warmup < 1 || blocks < 1 || samples_per_block < 1 || invocations < 1) {
            throw std::runtime_error("all benchmark counts must be positive");
        }

        const sycl::device device{sycl::gpu_selector_v};
        const sycl::context context{device};
        const auto async_handler = [](sycl::exception_list exceptions) {
            for (const auto & exception : exceptions) {
                try {
                    std::rethrow_exception(exception);
                } catch (const sycl::exception & error) {
                    std::cerr << "asynchronous_sycl_error=" << error.what() << '\n';
                }
            }
        };
        sycl::queue queue{context, device, async_handler,
                          sycl::property::queue::in_order{}};
        const auto engine = dnnl::sycl_interop::make_engine(device, context);
        auto stream = dnnl::sycl_interop::make_stream(engine, queue);

        const size_t a_elems = static_cast<size_t>(m * k);
        const size_t b_elems = static_cast<size_t>(k * n);
        const size_t c_elems = static_cast<size_t>(m * n);
        auto * a = sycl::malloc_device<sycl::half>(a_elems, queue);
        auto * b = sycl::malloc_device<sycl::half>(b_elems, queue);
        auto * rebuilt_c = sycl::malloc_device<float>(c_elems, queue);
        auto * cached_c = sycl::malloc_device<float>(c_elems, queue);
        if (!a || !b || !rebuilt_c || !cached_c) {
            throw std::runtime_error("device allocation failed");
        }

        queue.parallel_for(sycl::range<1>(a_elems), [=](sycl::id<1> idx) {
            const uint32_t i = static_cast<uint32_t>(idx[0]);
            a[i] = sycl::half(static_cast<float>(
                static_cast<int>((i * 17u + 3u) % 257u) - 128) / 512.0f);
        });
        queue.parallel_for(sycl::range<1>(b_elems), [=](sycl::id<1> idx) {
            const uint32_t i = static_cast<uint32_t>(idx[0]);
            b[i] = sycl::half(static_cast<float>(
                static_cast<int>((i * 13u + 7u) % 263u) - 131) / 512.0f);
        });
        queue.wait_and_throw();

        const Plan cached_plan(engine);
        const size_t scratchpad_size = std::max<size_t>(
            1, cached_plan.scratchpad_md.get_size());
        void * scratchpad = sycl::malloc_device(scratchpad_size, queue);
        if (!scratchpad) {
            throw std::runtime_error("scratchpad allocation failed");
        }

        const auto run_rebuilt = [&]() {
            for (int i = 0; i < invocations; ++i) {
                const Plan rebuilt_plan(engine);
                if (rebuilt_plan.scratchpad_md.get_size() > scratchpad_size) {
                    throw std::runtime_error("reconstructed scratchpad grew");
                }
                execute_plan(rebuilt_plan, engine, stream, a, b, rebuilt_c, scratchpad);
            }
            queue.wait_and_throw();
        };
        const auto run_cached = [&]() {
            for (int i = 0; i < invocations; ++i) {
                execute_plan(cached_plan, engine, stream, a, b, cached_c, scratchpad);
            }
            queue.wait_and_throw();
        };

        for (int i = 0; i < warmup; ++i) {
            run_rebuilt();
            run_cached();
        }

        std::vector<double> rebuilt_ms;
        std::vector<double> cached_ms;
        rebuilt_ms.reserve(static_cast<size_t>(blocks * samples_per_block));
        cached_ms.reserve(static_cast<size_t>(blocks * samples_per_block));
        for (int block = 0; block < blocks; ++block) {
            for (int sample = 0; sample < samples_per_block; ++sample) {
                if ((block + sample) % 2 == 0) {
                    rebuilt_ms.push_back(timed_per_invocation_ms(run_rebuilt, invocations));
                    cached_ms.push_back(timed_per_invocation_ms(run_cached, invocations));
                } else {
                    cached_ms.push_back(timed_per_invocation_ms(run_cached, invocations));
                    rebuilt_ms.push_back(timed_per_invocation_ms(run_rebuilt, invocations));
                }
            }
        }

        run_rebuilt();
        run_cached();
        std::vector<uint8_t> host_rebuilt(c_elems * sizeof(float));
        std::vector<uint8_t> host_cached(c_elems * sizeof(float));
        queue.memcpy(host_rebuilt.data(), rebuilt_c, host_rebuilt.size());
        queue.memcpy(host_cached.data(), cached_c, host_cached.size());
        queue.wait_and_throw();
        const bool output_exact = host_rebuilt == host_cached;

        const double rebuilt_median = percentile(rebuilt_ms, 0.5);
        const double cached_median = percentile(cached_ms, 0.5);
        std::cout << std::fixed << std::setprecision(6)
                  << "device_name=" << device.get_info<sycl::info::device::name>() << '\n'
                  << "driver_version=" << device.get_info<sycl::info::device::driver_version>() << '\n'
                  << "m=" << m << '\n'
                  << "n=" << n << '\n'
                  << "k=" << k << '\n'
                  << "samples_per_arm=" << rebuilt_ms.size() << '\n'
                  << "invocations_per_sample=" << invocations << '\n'
                  << "scratchpad_bytes=" << scratchpad_size << '\n'
                  << "rebuilt_p25_ms=" << percentile(rebuilt_ms, 0.25) << '\n'
                  << "rebuilt_median_ms=" << rebuilt_median << '\n'
                  << "rebuilt_p75_ms=" << percentile(rebuilt_ms, 0.75) << '\n'
                  << "cached_p25_ms=" << percentile(cached_ms, 0.25) << '\n'
                  << "cached_median_ms=" << cached_median << '\n'
                  << "cached_p75_ms=" << percentile(cached_ms, 0.75) << '\n'
                  << "median_speedup=" << rebuilt_median / cached_median << '\n'
                  << "median_reduction_percent="
                  << (rebuilt_median - cached_median) / rebuilt_median * 100.0 << '\n'
                  << "output_byte_exact=" << (output_exact ? "true" : "false") << '\n';

        sycl::free(a, queue);
        sycl::free(b, queue);
        sycl::free(rebuilt_c, queue);
        sycl::free(cached_c, queue);
        sycl::free(scratchpad, queue);
        return output_exact ? 0 : 2;
    } catch (const std::exception & error) {
        std::cerr << "error=" << error.what() << '\n';
        return 1;
    }
}
