#include <sycl/sycl.hpp>
#include <sycl/ext/intel/esimd.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace esimd = sycl::ext::intel::esimd;
namespace xmx = sycl::ext::intel::esimd::xmx;

// Guarded verifier experiment, deliberately independent of llama.cpp.  One
// DPAS consumes exactly one Q4_0/Q8_1 block: A is Mx32 signed INT8 and B is
// 32x16 signed INT4.  Q4_0 and Q8_1 scales are applied after each block DPAS.
struct problem {
    int m;
    int k;
    int n;
    int iterations;
};

static size_t weight_nibble_index(int kb, int tile, int k_inner, int n_inner, int n_tiles) {
    // Xe VNNI B layout for s4: [K/8][N][8 packed K values].  The eight
    // adjacent nibbles form one 32-bit VNNI word.
    return (((size_t(kb) * n_tiles + tile) * 4 + k_inner / 8) * 16 + n_inner) * 8 + k_inner % 8;
}

static int8_t unpack_s4(const uint8_t * packed, size_t nibble) {
    const uint8_t u = (packed[nibble / 2] >> (4 * (nibble & 1))) & 0x0f;
    return static_cast<int8_t>(u < 8 ? u : int(u) - 16);
}

template <int M>
class dpas_verifier_kernel;

template <int M, int SPLITS>
class dpas_verifier_split_kernel;

template <int M, int SPLITS>
class dpas_verifier_reduce_kernel;

template <int M>
sycl::event launch_dpas(sycl::queue & q, const uint8_t * weights, const int8_t * activations,
                        const float * weight_scales, const float * activation_scales,
                        float * output, int k_blocks, int n_tiles) {
    return q.submit([&](sycl::handler & h) {
        h.parallel_for<dpas_verifier_kernel<M>>(sycl::range<1>(n_tiles), [=](sycl::id<1> id)
                                                 [[intel::sycl_explicit_simd]] {
            const int tile = id[0];
            esimd::simd<float, M * 16> accum(0.0f);

            for (int kb = 0; kb < k_blocks; ++kb) {
                // B is already offline packed in the exact byte order accepted
                // by DPAS.  Each tile is 32*16 s4 = 256 bytes.
                esimd::simd<uint32_t, 64> b;
                b.copy_from(reinterpret_cast<const uint32_t *>(weights) +
                            (size_t(kb) * n_tiles + tile) * 64);

                // A is row-major Mx32 s8 = M*8 dwords for this Q8_1 block.
                esimd::simd<uint32_t, M * 8> a;
                a.copy_from(reinterpret_cast<const uint32_t *>(activations) + size_t(kb) * M * 8);

                auto dots = xmx::dpas<8, M, int32_t, uint32_t, uint32_t,
                                      xmx::dpas_argument_type::s4,
                                      xmx::dpas_argument_type::s8>(b, a);
                for (int row = 0; row < M; ++row) {
                    const float as = activation_scales[kb * M + row];
                    for (int col = 0; col < 16; ++col) {
                        accum[row * 16 + col] +=
                            float(dots[row * 16 + col]) * as *
                            weight_scales[(size_t(kb) * n_tiles + tile) * 16 + col];
                    }
                }
            }

            for (int row = 0; row < M; ++row) {
                esimd::simd<float, 16> row_output = accum.template select<16, 1>(row * 16);
                row_output.copy_to(output + size_t(row) * n_tiles * 16 + tile * 16);
            }
        });
    });
}

template <int M, int SPLITS>
std::pair<sycl::event, sycl::event> launch_dpas_split(
        sycl::queue & q, const uint8_t * weights, const int8_t * activations,
        const float * weight_scales, const float * activation_scales,
        float * partial, float * output, int k_blocks, int n_tiles) {
    const sycl::event compute = q.submit([&](sycl::handler & h) {
        h.parallel_for<dpas_verifier_split_kernel<M, SPLITS>>(
            sycl::range<2>(SPLITS, n_tiles), [=](sycl::id<2> id)
                                               [[intel::sycl_explicit_simd]] {
                const int split = id[0];
                const int tile = id[1];
                const int kb_begin = (k_blocks * split) / SPLITS;
                const int kb_end = (k_blocks * (split + 1)) / SPLITS;
                esimd::simd<float, M * 16> accum(0.0f);

                for (int kb = kb_begin; kb < kb_end; ++kb) {
                    esimd::simd<uint32_t, 64> b;
                    b.copy_from(reinterpret_cast<const uint32_t *>(weights) +
                                (size_t(kb) * n_tiles + tile) * 64);
                    esimd::simd<uint32_t, M * 8> a;
                    a.copy_from(reinterpret_cast<const uint32_t *>(activations) + size_t(kb) * M * 8);
                    auto dots = xmx::dpas<8, M, int32_t, uint32_t, uint32_t,
                                          xmx::dpas_argument_type::s4,
                                          xmx::dpas_argument_type::s8>(b, a);
                    for (int row = 0; row < M; ++row) {
                        const float as = activation_scales[kb * M + row];
                        for (int col = 0; col < 16; ++col) {
                            accum[row * 16 + col] +=
                                float(dots[row * 16 + col]) * as *
                                weight_scales[(size_t(kb) * n_tiles + tile) * 16 + col];
                        }
                    }
                }
                for (int row = 0; row < M; ++row) {
                    esimd::simd<float, 16> row_output = accum.template select<16, 1>(row * 16);
                    row_output.copy_to(partial +
                        (size_t(split) * M + row) * n_tiles * 16 + tile * 16);
                }
            });
    });

    const sycl::event reduce = q.submit([&](sycl::handler & h) {
        h.depends_on(compute);
        h.parallel_for<dpas_verifier_reduce_kernel<M, SPLITS>>(
            sycl::range<2>(M, n_tiles * 16), [=](sycl::id<2> id) {
                const int row = id[0];
                const int col = id[1];
                float sum = 0.0f;
#pragma unroll
                for (int split = 0; split < SPLITS; ++split) {
                    sum += partial[(size_t(split) * M + row) * n_tiles * 16 + col];
                }
                output[size_t(row) * n_tiles * 16 + col] = sum;
            });
    });
    return {compute, reduce};
}

class repeated_vector_kernel;

sycl::event launch_repeated_vector(sycl::queue & q, const uint8_t * weights,
                                   const int8_t * activations, const float * weight_scales,
                                   const float * activation_scales, float * output,
                                   int m, int k_blocks, int n_tiles) {
    const int n = n_tiles * 16;
    return q.submit([&](sycl::handler & h) {
        h.parallel_for<repeated_vector_kernel>(sycl::range<2>(m, n), [=](sycl::id<2> id) {
            const int row = id[0];
            const int col = id[1];
            const int tile = col / 16;
            const int ni = col % 16;
            float sum = 0.0f;
            for (int kb = 0; kb < k_blocks; ++kb) {
                int dot = 0;
                for (int ki = 0; ki < 32; ++ki) {
                    const size_t nib = weight_nibble_index(kb, tile, ki, ni, n_tiles);
                    dot += int(activations[(size_t(kb) * m + row) * 32 + ki]) *
                           int(unpack_s4(weights, nib));
                }
                sum += float(dot) * activation_scales[kb * m + row] *
                       weight_scales[(size_t(kb) * n_tiles + tile) * 16 + ni];
            }
            output[size_t(row) * n + col] = sum;
        });
    });
}

static double event_us(const sycl::event & e) {
    const auto begin = e.get_profiling_info<sycl::info::event_profiling::command_start>();
    const auto end = e.get_profiling_info<sycl::info::event_profiling::command_end>();
    return double(end - begin) / 1000.0;
}

template <int M>
int run(const problem & p) {
    if (p.m != M || p.k % 32 || p.n % 16) {
        throw std::runtime_error("M must be 4 or 8, K a multiple of 32, and N a multiple of 16");
    }
    sycl::queue q{sycl::gpu_selector_v,
                  sycl::property_list{sycl::property::queue::enable_profiling{}}};
    const int k_blocks = p.k / 32;
    const int n_tiles = p.n / 16;
    const size_t weight_bytes = size_t(k_blocks) * n_tiles * 256;
    const size_t activation_bytes = size_t(k_blocks) * M * 32;
    const size_t weight_scale_count = size_t(k_blocks) * p.n;
    const size_t activation_scale_count = size_t(k_blocks) * M;
    const size_t output_count = size_t(M) * p.n;

    std::mt19937 rng(0xB70);
    std::uniform_int_distribution<int> q4(-8, 7);
    std::uniform_int_distribution<int> q8(-127, 127);
    std::uniform_real_distribution<float> scale(0.0005f, 0.08f);
    std::vector<uint8_t> packed(weight_bytes, 0);
    std::vector<int8_t> acts(activation_bytes);
    std::vector<float> ws(weight_scale_count), as(activation_scale_count);
    constexpr int reference_cols = 64;
    const int checked_cols = std::min(p.n, reference_cols);
    std::vector<float> reference(size_t(M) * checked_cols, 0.0f);
    std::vector<float> dpas_out(output_count), split4_out(output_count), split8_out(output_count), vector_out(output_count);

    for (int kb = 0; kb < k_blocks; ++kb) {
        for (int tile = 0; tile < n_tiles; ++tile) {
            for (int ni = 0; ni < 16; ++ni) {
                ws[(size_t(kb) * n_tiles + tile) * 16 + ni] = scale(rng);
                for (int ki = 0; ki < 32; ++ki) {
                    const size_t nib = weight_nibble_index(kb, tile, ki, ni, n_tiles);
                    // DPAS s4 consumes two's-complement nibbles. Ordinary
                    // Q4_0 stores the same value as (nibble - 8), so an
                    // offline GGUF packer must flip bit 3 (nibble ^ 8).
                    const uint8_t v = uint8_t(q4(rng)) & 0x0f;
                    packed[nib / 2] |= v << (4 * (nib & 1));
                }
            }
        }
        for (int row = 0; row < M; ++row) {
            as[kb * M + row] = scale(rng);
            for (int ki = 0; ki < 32; ++ki) {
                acts[(size_t(kb) * M + row) * 32 + ki] = int8_t(q8(rng));
            }
        }
    }

    for (int row = 0; row < M; ++row) {
        for (int col = 0; col < checked_cols; ++col) {
            const int tile = col / 16, ni = col % 16;
            for (int kb = 0; kb < k_blocks; ++kb) {
                int dot = 0;
                for (int ki = 0; ki < 32; ++ki) {
                    dot += int(acts[(size_t(kb) * M + row) * 32 + ki]) *
                           int(unpack_s4(packed.data(), weight_nibble_index(kb, tile, ki, ni, n_tiles)));
                }
                reference[size_t(row) * checked_cols + col] += float(dot) * as[kb * M + row] *
                    ws[(size_t(kb) * n_tiles + tile) * 16 + ni];
            }
        }
    }

    auto * dw = sycl::malloc_device<uint8_t>(weight_bytes, q);
    auto * da = sycl::malloc_device<int8_t>(activation_bytes, q);
    auto * dws = sycl::malloc_device<float>(weight_scale_count, q);
    auto * das = sycl::malloc_device<float>(activation_scale_count, q);
    auto * dout = sycl::malloc_device<float>(output_count, q);
    auto * dpartial = sycl::malloc_device<float>(8 * output_count, q);
    q.memcpy(dw, packed.data(), weight_bytes);
    q.memcpy(da, acts.data(), activation_bytes);
    q.memcpy(dws, ws.data(), weight_scale_count * sizeof(float));
    q.memcpy(das, as.data(), activation_scale_count * sizeof(float)).wait();

    launch_dpas<M>(q, dw, da, dws, das, dout, k_blocks, n_tiles).wait();
    q.memcpy(dpas_out.data(), dout, output_count * sizeof(float)).wait();
    launch_dpas_split<M, 4>(q, dw, da, dws, das, dpartial, dout, k_blocks, n_tiles).second.wait();
    q.memcpy(split4_out.data(), dout, output_count * sizeof(float)).wait();
    launch_dpas_split<M, 8>(q, dw, da, dws, das, dpartial, dout, k_blocks, n_tiles).second.wait();
    q.memcpy(split8_out.data(), dout, output_count * sizeof(float)).wait();
    launch_repeated_vector(q, dw, da, dws, das, dout, M, k_blocks, n_tiles).wait();
    q.memcpy(vector_out.data(), dout, output_count * sizeof(float)).wait();

    float dpas_max_abs = 0.0f, split4_max_abs = 0.0f, split8_max_abs = 0.0f;
    float vector_max_abs = 0.0f, kernel_max_abs = 0.0f;
    for (size_t i = 0; i < output_count; ++i) {
        kernel_max_abs = std::max(kernel_max_abs, std::abs(dpas_out[i] - vector_out[i]));
        split4_max_abs = std::max(split4_max_abs, std::abs(split4_out[i] - vector_out[i]));
        split8_max_abs = std::max(split8_max_abs, std::abs(split8_out[i] - vector_out[i]));
    }
    for (int row = 0; row < M; ++row) {
        for (int col = 0; col < checked_cols; ++col) {
            const size_t oi = size_t(row) * p.n + col;
            const size_t ri = size_t(row) * checked_cols + col;
            dpas_max_abs = std::max(dpas_max_abs, std::abs(dpas_out[oi] - reference[ri]));
            vector_max_abs = std::max(vector_max_abs, std::abs(vector_out[oi] - reference[ri]));
        }
    }
    const float tolerance = 2e-3f;
    if (dpas_max_abs > tolerance || vector_max_abs > tolerance || kernel_max_abs > tolerance ||
        split4_max_abs > tolerance || split8_max_abs > tolerance) {
        std::cerr << "FAIL correctness dpas_max_abs=" << dpas_max_abs
                  << " vector_max_abs=" << vector_max_abs
                  << " kernel_max_abs=" << kernel_max_abs
                  << " split4_max_abs=" << split4_max_abs
                  << " split8_max_abs=" << split8_max_abs
                  << " tolerance=" << tolerance << '\n';
        return 2;
    }

    std::vector<double> dpas_us, dpas_wall_us, split4_us, split4_wall_us;
    std::vector<double> split8_us, split8_wall_us, vector_us, vector_wall_us;
    dpas_us.reserve(p.iterations);
    vector_us.reserve(p.iterations);
    for (int i = 0; i < p.iterations; ++i) {
        auto wall_begin = std::chrono::steady_clock::now();
        auto de = launch_dpas<M>(q, dw, da, dws, das, dout, k_blocks, n_tiles);
        de.wait();
        auto wall_end = std::chrono::steady_clock::now();
        dpas_us.push_back(event_us(de));
        dpas_wall_us.push_back(std::chrono::duration<double, std::micro>(wall_end - wall_begin).count());

        wall_begin = std::chrono::steady_clock::now();
        auto s4 = launch_dpas_split<M, 4>(q, dw, da, dws, das, dpartial, dout, k_blocks, n_tiles);
        s4.second.wait();
        wall_end = std::chrono::steady_clock::now();
        split4_us.push_back(event_us(s4.first) + event_us(s4.second));
        split4_wall_us.push_back(std::chrono::duration<double, std::micro>(wall_end - wall_begin).count());

        wall_begin = std::chrono::steady_clock::now();
        auto s8 = launch_dpas_split<M, 8>(q, dw, da, dws, das, dpartial, dout, k_blocks, n_tiles);
        s8.second.wait();
        wall_end = std::chrono::steady_clock::now();
        split8_us.push_back(event_us(s8.first) + event_us(s8.second));
        split8_wall_us.push_back(std::chrono::duration<double, std::micro>(wall_end - wall_begin).count());

        wall_begin = std::chrono::steady_clock::now();
        auto ve = launch_repeated_vector(q, dw, da, dws, das, dout, M, k_blocks, n_tiles);
        ve.wait();
        wall_end = std::chrono::steady_clock::now();
        vector_us.push_back(event_us(ve));
        vector_wall_us.push_back(std::chrono::duration<double, std::micro>(wall_end - wall_begin).count());
    }
    const auto median = [](std::vector<double> x) {
        std::sort(x.begin(), x.end());
        return x[x.size() / 2];
    };
    const double du = median(dpas_us), dwall = median(dpas_wall_us);
    const double s4u = median(split4_us), s4wall = median(split4_wall_us);
    const double s8u = median(split8_us), s8wall = median(split8_wall_us);
    const double vu = median(vector_us), vwall = median(vector_wall_us);
    const double original_speedup = vwall / dwall;
    const double split4_speedup = vwall / s4wall;
    const double split8_speedup = vwall / s8wall;
    const double rescue_speedup = std::max(split4_speedup, split8_speedup);
    std::cout << std::fixed << std::setprecision(3)
              << "device=\"" << q.get_device().get_info<sycl::info::device::name>() << "\""
              << " M=" << M << " K=" << p.k << " N=" << p.n
              << " original_event_us=" << du << " original_wall_us=" << dwall
              << " split4_event_us=" << s4u << " split4_wall_us=" << s4wall
              << " split8_event_us=" << s8u << " split8_wall_us=" << s8wall
              << " vector_event_us=" << vu << " vector_wall_us=" << vwall
              << " original_speedup=" << original_speedup
              << " split4_speedup=" << split4_speedup
              << " split8_speedup=" << split8_speedup
              << " dpas_max_abs=" << dpas_max_abs
              << " vector_max_abs=" << vector_max_abs << " kernel_max_abs=" << kernel_max_abs
              << " split4_max_abs=" << split4_max_abs << " split8_max_abs=" << split8_max_abs
              << " gate=" << (rescue_speedup >= 1.5 ? "PASS" : "FAIL") << '\n';

    sycl::free(dw, q); sycl::free(da, q); sycl::free(dws, q);
    sycl::free(das, q); sycl::free(dout, q); sycl::free(dpartial, q);
    return rescue_speedup >= 1.5 ? 0 : 3;
}

int main(int argc, char ** argv) {
    problem p{4, 5120, 5120, 30};
    if (argc > 1) p.m = std::stoi(argv[1]);
    if (argc > 2) p.k = std::stoi(argv[2]);
    if (argc > 3) p.n = std::stoi(argv[3]);
    if (argc > 4) p.iterations = std::stoi(argv[4]);
    try {
        if (p.m == 4) return run<4>(p);
        if (p.m == 8) return run<8>(p);
        throw std::runtime_error("only verifier widths M=4 and M=8 are compiled");
    } catch (const std::exception & e) {
        std::cerr << "ERROR: " << e.what() << '\n';
        return 1;
    }
}
