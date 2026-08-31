#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include <sycl/sycl.hpp>
#include <oneapi/dnnl/dnnl.hpp>
#include <oneapi/dnnl/dnnl_sycl.hpp>

namespace {

using clock_type = std::chrono::steady_clock;
using dt = dnnl::memory::data_type;

struct Gemm {
    dnnl::matmul primitive;
    dnnl::memory a;
    dnnl::memory b;
    dnnl::memory c;
    dnnl::memory scratchpad;
    void * scratchpad_ptr = nullptr;

    Gemm(const dnnl::engine & engine, int64_t m, int64_t n, int64_t k,
         void * a_ptr, void * b_ptr, void * c_ptr, sycl::queue & queue) {
        const dnnl::memory::dims a_dims = {1, m, k};
        const dnnl::memory::dims b_dims = {1, k, n};
        const dnnl::memory::dims c_dims = {1, m, n};
        const auto a_md = dnnl::memory::desc(a_dims, dt::f16, {m * k, k, 1});
        const auto b_md = dnnl::memory::desc(b_dims, dt::f16, {k * n, 1, k});
        const auto c_md = dnnl::memory::desc(c_dims, dt::f32, {m * n, 1, m});

        dnnl::primitive_attr attr;
        attr.set_scratchpad_mode(dnnl::scratchpad_mode::user);
        attr.set_deterministic(true);
        const auto pd = dnnl::matmul::primitive_desc(engine, a_md, b_md, c_md, attr);

        a = dnnl::memory(a_md, engine, a_ptr);
        b = dnnl::memory(b_md, engine, b_ptr);
        c = dnnl::memory(pd.dst_desc(), engine, c_ptr);
        const auto scratchpad_md = pd.scratchpad_desc();
        scratchpad_ptr = sycl::malloc_device(std::max<size_t>(1, scratchpad_md.get_size()), queue);
        if (scratchpad_ptr == nullptr) {
            throw std::runtime_error("scratchpad allocation failed");
        }
        scratchpad = dnnl::memory(scratchpad_md, engine, scratchpad_ptr);
        primitive = dnnl::matmul(pd);
    }

    void execute(dnnl::stream & stream) {
        primitive.execute(stream, {
            {DNNL_ARG_SRC, a},
            {DNNL_ARG_WEIGHTS, b},
            {DNNL_ARG_DST, c},
            {DNNL_ARG_SCRATCHPAD, scratchpad},
        });
    }
};

double percentile(std::vector<double> values, double q) {
    std::sort(values.begin(), values.end());
    const double pos = q * static_cast<double>(values.size() - 1);
    const size_t lo = static_cast<size_t>(std::floor(pos));
    const size_t hi = static_cast<size_t>(std::ceil(pos));
    const double frac = pos - static_cast<double>(lo);
    return values[lo] * (1.0 - frac) + values[hi] * frac;
}

template <typename Fn>
double timed_ms(Fn && fn) {
    const auto start = clock_type::now();
    fn();
    return std::chrono::duration<double, std::milli>(clock_type::now() - start).count();
}

} // namespace

int main(int argc, char ** argv) {
    try {
        const int warmup = argc > 1 ? std::stoi(argv[1]) : 8;
        const int blocks = argc > 2 ? std::stoi(argv[2]) : 6;
        const int samples_per_block = argc > 3 ? std::stoi(argv[3]) : 10;
        constexpr int64_t m = 8704;
        constexpr int64_t n = 96;
        constexpr int64_t k = 5120;

        const sycl::device device{sycl::gpu_selector_v};
        const sycl::context context{device};
        const auto async_handler = [](sycl::exception_list exceptions) {
            for (const auto & exception : exceptions) {
                try {
                    std::rethrow_exception(exception);
                } catch (const sycl::exception & error) {
                    std::cerr << "asynchronous SYCL error: " << error.what() << '\n';
                }
            }
        };
        sycl::queue q0{context, device, async_handler, sycl::property::queue::in_order{}};
        sycl::queue q1{context, device, async_handler, sycl::property::queue::in_order{}};
        const auto engine = dnnl::sycl_interop::make_engine(device, context);
        auto stream0 = dnnl::sycl_interop::make_stream(engine, q0);
        auto stream1 = dnnl::sycl_interop::make_stream(engine, q1);

        const size_t a_elems = static_cast<size_t>(m * k);
        const size_t b_elems = static_cast<size_t>(k * n);
        const size_t c_elems = static_cast<size_t>(m * n);
        auto * a_gate = sycl::malloc_device<sycl::half>(a_elems, q0);
        auto * a_up = sycl::malloc_device<sycl::half>(a_elems, q0);
        auto * b = sycl::malloc_device<sycl::half>(b_elems, q0);
        auto * serial_gate = sycl::malloc_device<float>(c_elems, q0);
        auto * serial_up = sycl::malloc_device<float>(c_elems, q0);
        auto * concurrent_gate = sycl::malloc_device<float>(c_elems, q0);
        auto * concurrent_up = sycl::malloc_device<float>(c_elems, q0);
        if (!a_gate || !a_up || !b || !serial_gate || !serial_up || !concurrent_gate || !concurrent_up) {
            throw std::runtime_error("device allocation failed");
        }

        q0.parallel_for(sycl::range<1>(a_elems), [=](sycl::id<1> idx) {
            const uint32_t i = static_cast<uint32_t>(idx[0]);
            a_gate[i] = sycl::half(static_cast<float>(static_cast<int>((i * 17u + 3u) % 257u) - 128) / 512.0f);
            a_up[i] = sycl::half(static_cast<float>(static_cast<int>((i * 29u + 11u) % 251u) - 125) / 512.0f);
        });
        q0.parallel_for(sycl::range<1>(b_elems), [=](sycl::id<1> idx) {
            const uint32_t i = static_cast<uint32_t>(idx[0]);
            b[i] = sycl::half(static_cast<float>(static_cast<int>((i * 13u + 7u) % 263u) - 131) / 512.0f);
        });
        q0.wait_and_throw();

        Gemm serial_g(engine, m, n, k, a_gate, b, serial_gate, q0);
        Gemm serial_u(engine, m, n, k, a_up, b, serial_up, q0);
        Gemm concurrent_g(engine, m, n, k, a_gate, b, concurrent_gate, q0);
        Gemm concurrent_u(engine, m, n, k, a_up, b, concurrent_up, q1);

        const auto run_serial = [&]() {
            serial_g.execute(stream0);
            serial_u.execute(stream0);
            q0.wait_and_throw();
        };
        const auto run_concurrent = [&]() {
            concurrent_g.execute(stream0);
            concurrent_u.execute(stream1);
            q0.wait_and_throw();
            q1.wait_and_throw();
        };
        for (int i = 0; i < warmup; ++i) {
            run_serial();
            run_concurrent();
        }

        std::vector<double> serial_ms;
        std::vector<double> concurrent_ms;
        serial_ms.reserve(static_cast<size_t>(blocks * samples_per_block));
        concurrent_ms.reserve(static_cast<size_t>(blocks * samples_per_block));
        for (int block = 0; block < blocks; ++block) {
            for (int sample = 0; sample < samples_per_block; ++sample) {
                if ((block + sample) % 2 == 0) {
                    serial_ms.push_back(timed_ms(run_serial));
                    concurrent_ms.push_back(timed_ms(run_concurrent));
                } else {
                    concurrent_ms.push_back(timed_ms(run_concurrent));
                    serial_ms.push_back(timed_ms(run_serial));
                }
            }
        }

        run_serial();
        run_concurrent();
        std::vector<uint8_t> host_serial_gate(c_elems * sizeof(float));
        std::vector<uint8_t> host_serial_up(c_elems * sizeof(float));
        std::vector<uint8_t> host_concurrent_gate(c_elems * sizeof(float));
        std::vector<uint8_t> host_concurrent_up(c_elems * sizeof(float));
        q0.memcpy(host_serial_gate.data(), serial_gate, host_serial_gate.size());
        q0.memcpy(host_serial_up.data(), serial_up, host_serial_up.size());
        q0.memcpy(host_concurrent_gate.data(), concurrent_gate, host_concurrent_gate.size());
        q0.memcpy(host_concurrent_up.data(), concurrent_up, host_concurrent_up.size());
        q0.wait_and_throw();
        const bool gate_exact = host_serial_gate == host_concurrent_gate;
        const bool up_exact = host_serial_up == host_concurrent_up;

        const double serial_median = percentile(serial_ms, 0.5);
        const double concurrent_median = percentile(concurrent_ms, 0.5);
        std::cout << std::fixed << std::setprecision(6)
                  << "device_name=" << device.get_info<sycl::info::device::name>() << '\n'
                  << "driver_version=" << device.get_info<sycl::info::device::driver_version>() << '\n'
                  << "m=" << m << '\n'
                  << "n=" << n << '\n'
                  << "k=" << k << '\n'
                  << "samples_per_arm=" << serial_ms.size() << '\n'
                  << "serial_p25_ms=" << percentile(serial_ms, 0.25) << '\n'
                  << "serial_median_ms=" << serial_median << '\n'
                  << "serial_p75_ms=" << percentile(serial_ms, 0.75) << '\n'
                  << "concurrent_p25_ms=" << percentile(concurrent_ms, 0.25) << '\n'
                  << "concurrent_median_ms=" << concurrent_median << '\n'
                  << "concurrent_p75_ms=" << percentile(concurrent_ms, 0.75) << '\n'
                  << "median_speedup=" << serial_median / concurrent_median << '\n'
                  << "median_reduction_percent=" << (serial_median - concurrent_median) / serial_median * 100.0 << '\n'
                  << "gate_byte_exact=" << (gate_exact ? "true" : "false") << '\n'
                  << "up_byte_exact=" << (up_exact ? "true" : "false") << '\n';

        sycl::free(a_gate, q0);
        sycl::free(a_up, q0);
        sycl::free(b, q0);
        sycl::free(serial_gate, q0);
        sycl::free(serial_up, q0);
        sycl::free(concurrent_gate, q0);
        sycl::free(concurrent_up, q0);
        sycl::free(serial_g.scratchpad_ptr, q0);
        sycl::free(serial_u.scratchpad_ptr, q0);
        sycl::free(concurrent_g.scratchpad_ptr, q0);
        sycl::free(concurrent_u.scratchpad_ptr, q1);
        return gate_exact && up_exact ? 0 : 2;
    } catch (const std::exception & error) {
        std::cerr << "error=" << error.what() << '\n';
        return 1;
    }
}
