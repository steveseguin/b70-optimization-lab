#include <sycl/sycl.hpp>
#include <sycl/ext/intel/esimd.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <random>
#include <vector>

namespace esimd = sycl::ext::intel::esimd;
namespace xmx   = sycl::ext::intel::esimd::xmx;

constexpr int M = 6;
constexpr int K = 17408;
constexpr int N = 5120;
constexpr int QK = 32;
constexpr int LANES = 16;

struct q8_meta {
    float d;
    float correction;
};

class swiglu_store_kernel;
class canonical_quant_kernel;
class canonical_repack_kernel;
class direct_quant_kernel;
class fused_swiglu_quant_kernel;
template<bool AddResidual> class down_dpas_kernel;
class residual_add_kernel;

static double event_us(const sycl::event & event) {
    return double(event.get_profiling_info<sycl::info::event_profiling::command_end>() -
                  event.get_profiling_info<sycl::info::event_profiling::command_start>()) / 1000.0;
}

static double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    const size_t middle = values.size()/2;
    return values.size()%2 ? values[middle] : (values[middle - 1] + values[middle])/2.0;
}

static sycl::event swiglu_store(
        sycl::queue & queue, const float * gate, const float * up, float * output) {
    constexpr size_t count = size_t(M)*K;
    constexpr size_t local = 256;
    return queue.submit([&](sycl::handler & cgh) {
        cgh.parallel_for<swiglu_store_kernel>(
                sycl::nd_range<1>(((count + local - 1)/local)*local, local),
                [=](sycl::nd_item<1> item) {
            const size_t index = item.get_global_linear_id();
            if (index >= count) {
                return;
            }
            const float x = gate[index];
            volatile float silu = x/(1.0f + sycl::exp(-x));
            output[index] = silu*up[index];
        });
    });
}

static sycl::event canonical_quant(
        sycl::queue & queue, const float * input, int8_t * canonical) {
    constexpr int kb = K/QK;
    constexpr int values_per_lane = QK/LANES;
    return queue.submit([&](sycl::handler & cgh) {
        cgh.parallel_for<canonical_quant_kernel>(
                sycl::nd_range<1>(M*kb*LANES, LANES), [=](sycl::nd_item<1> item)
                [[sycl::reqd_sub_group_size(LANES)]] {
            const int linear = item.get_group(0);
            const int row = linear/kb;
            const int block = linear%kb;
            const int lane = item.get_local_id(0);
            float values[values_per_lane];
            float sum = 0.0f;
            float amax = 0.0f;
#pragma unroll
            for (int i = 0; i < values_per_lane; ++i) {
                const int element = lane*values_per_lane + i;
                const float value = input[size_t(row)*K + block*QK + element];
                values[i] = value;
                sum += value;
                amax = sycl::fmax(amax, sycl::fabs(value));
            }
            const auto subgroup = item.get_sub_group();
            amax = sycl::reduce_over_group(subgroup, amax, sycl::maximum<float>());
            sum = sycl::reduce_over_group(subgroup, sum, sycl::plus<float>());
            const float quant_d = amax != 0.0f ? amax/127.0f : 1.0f;
#pragma unroll
            for (int i = 0; i < values_per_lane; ++i) {
                const int element = lane*values_per_lane + i;
                canonical[size_t(row)*(K + kb*4) + block*QK + element] =
                        int8_t(sycl::round(values[i]/quant_d));
            }
            if (lane == 0) {
                auto * ds = reinterpret_cast<sycl::half2 *>(
                        canonical + size_t(row)*(K + kb*4) + K + block*4);
                *ds = sycl::half2(
                        sycl::half(amax != 0.0f ? quant_d : 0.0f), sycl::half(sum));
            }
        });
    });
}

static sycl::event canonical_repack(
        sycl::queue & queue, const int8_t * canonical, int8_t * soa) {
    constexpr int kb = K/QK;
    constexpr int values_per_lane = QK/LANES;
    return queue.submit([&](sycl::handler & cgh) {
        cgh.parallel_for<canonical_repack_kernel>(
                sycl::nd_range<1>(M*kb*LANES, LANES), [=](sycl::nd_item<1> item)
                [[sycl::reqd_sub_group_size(LANES)]] {
            const int linear = item.get_group(0);
            const int row = linear/kb;
            const int block = linear%kb;
            const int lane = item.get_local_id(0);
            int lane_qsum = 0;
#pragma unroll
            for (int i = 0; i < values_per_lane; ++i) {
                const int element = lane*values_per_lane + i;
                const int q = int(canonical[size_t(row)*(K + kb*4) + block*QK + element]);
                soa[(size_t(block)*M + row)*QK + element] = int8_t(q);
                lane_qsum += q;
            }
            const int qsum = sycl::reduce_over_group(
                    item.get_sub_group(), lane_qsum, sycl::plus<int>());
            if (lane == 0) {
                const auto ds = *reinterpret_cast<const sycl::half2 *>(
                        canonical + size_t(row)*(K + kb*4) + K + block*4);
                const float d = float(ds[0]);
                const float sum = float(ds[1]);
                auto * meta = reinterpret_cast<q8_meta *>(soa + size_t(M)*K);
                meta[block*M + row] = {d, 8.0f*(qsum*d - sum)};
            }
        });
    });
}

static sycl::event fused_swiglu_quant(
        sycl::queue & queue, const float * gate, const float * up, int8_t * soa) {
    constexpr int kb = K/QK;
    constexpr int values_per_lane = QK/LANES;
    return queue.submit([&](sycl::handler & cgh) {
        cgh.parallel_for<fused_swiglu_quant_kernel>(
                sycl::nd_range<1>(M*kb*LANES, LANES), [=](sycl::nd_item<1> item)
                [[sycl::reqd_sub_group_size(LANES)]] {
            const int linear = item.get_group(0);
            const int row = linear/kb;
            const int block = linear%kb;
            const int lane = item.get_local_id(0);
            float values[values_per_lane];
            float sum = 0.0f;
            float amax = 0.0f;
#pragma unroll
            for (int i = 0; i < values_per_lane; ++i) {
                const int element = lane*values_per_lane + i;
                const size_t offset = size_t(row)*K + block*QK + element;
                const float x = gate[offset];
                // Match the repaired runtime fusion's explicit SiLU F32
                // rounding point before multiplication by the up branch.
                volatile float silu = x/(1.0f + sycl::exp(-x));
                // Materialize the product as F32 as well. The unfused path
                // stores this value to an F32 tensor before quantization.
                volatile float value = silu*up[offset];
                values[i] = value;
                sum += value;
                amax = sycl::fmax(amax, sycl::fabs(value));
            }
            const auto subgroup = item.get_sub_group();
            amax = sycl::reduce_over_group(subgroup, amax, sycl::maximum<float>());
            sum = sycl::reduce_over_group(subgroup, sum, sycl::plus<float>());
            const float quant_d = amax != 0.0f ? amax/127.0f : 1.0f;
            int lane_qsum = 0;
#pragma unroll
            for (int i = 0; i < values_per_lane; ++i) {
                const int element = lane*values_per_lane + i;
                const int q = int(sycl::round(values[i]/quant_d));
                soa[(size_t(block)*M + row)*QK + element] = int8_t(q);
                lane_qsum += q;
            }
            const int qsum = sycl::reduce_over_group(subgroup, lane_qsum, sycl::plus<int>());
            if (lane == 0) {
                // A volatile half materializes the production Q8_1
                // float->half->float boundary without the canonical tensor.
                volatile uint16_t hd_bits = sycl::bit_cast<uint16_t>(
                        sycl::half(amax != 0.0f ? quant_d : 0.0f));
                volatile uint16_t hs_bits = sycl::bit_cast<uint16_t>(sycl::half(sum));
                const float d = float(sycl::bit_cast<sycl::half>(uint16_t(hd_bits)));
                const float half_sum = float(sycl::bit_cast<sycl::half>(uint16_t(hs_bits)));
                auto * meta = reinterpret_cast<q8_meta *>(soa + size_t(M)*K);
                meta[block*M + row] = {d, 8.0f*(qsum*d - half_sum)};
            }
        });
    });
}

static sycl::event direct_quant(
        sycl::queue & queue, const float * input, int8_t * soa) {
    constexpr int kb = K/QK;
    constexpr int values_per_lane = QK/LANES;
    return queue.submit([&](sycl::handler & cgh) {
        cgh.parallel_for<direct_quant_kernel>(
                sycl::nd_range<1>(M*kb*LANES, LANES), [=](sycl::nd_item<1> item)
                [[sycl::reqd_sub_group_size(LANES)]] {
            const int linear = item.get_group(0);
            const int row = linear/kb;
            const int block = linear%kb;
            const int lane = item.get_local_id(0);
            float values[values_per_lane];
            float sum = 0.0f;
            float amax = 0.0f;
#pragma unroll
            for (int i = 0; i < values_per_lane; ++i) {
                const int element = lane*values_per_lane + i;
                const float value = input[size_t(row)*K + block*QK + element];
                values[i] = value;
                sum += value;
                amax = sycl::fmax(amax, sycl::fabs(value));
            }
            const auto subgroup = item.get_sub_group();
            amax = sycl::reduce_over_group(subgroup, amax, sycl::maximum<float>());
            sum = sycl::reduce_over_group(subgroup, sum, sycl::plus<float>());
            const float quant_d = amax != 0.0f ? amax/127.0f : 1.0f;
            int lane_qsum = 0;
#pragma unroll
            for (int i = 0; i < values_per_lane; ++i) {
                const int element = lane*values_per_lane + i;
                const int q = int(sycl::round(values[i]/quant_d));
                soa[(size_t(block)*M + row)*QK + element] = int8_t(q);
                lane_qsum += q;
            }
            const int qsum = sycl::reduce_over_group(subgroup, lane_qsum, sycl::plus<int>());
            if (lane == 0) {
                volatile uint16_t hd_bits = sycl::bit_cast<uint16_t>(
                        sycl::half(amax != 0.0f ? quant_d : 0.0f));
                volatile uint16_t hs_bits = sycl::bit_cast<uint16_t>(sycl::half(sum));
                const float d = float(sycl::bit_cast<sycl::half>(uint16_t(hd_bits)));
                const float half_sum = float(sycl::bit_cast<sycl::half>(uint16_t(hs_bits)));
                auto * meta = reinterpret_cast<q8_meta *>(soa + size_t(M)*K);
                meta[block*M + row] = {d, 8.0f*(qsum*d - half_sum)};
            }
        });
    });
}

template<bool AddResidual>
static sycl::event down_dpas(
        sycl::queue & queue, const uint8_t * weights, const int8_t * activations,
        const float * residual, float * output) {
    constexpr int splits = 8;
    constexpr int joint = 2;
    constexpr int slm_floats = splits*joint*M*16;
    constexpr int kb = K/QK;
    constexpr int nt = N/16;
    constexpr int pairs = (nt + joint - 1)/joint;
    constexpr size_t quant_bytes = size_t(K)*N/2;
    const auto * meta = reinterpret_cast<const q8_meta *>(activations + size_t(M)*K);
    return queue.submit([&](sycl::handler & cgh) {
        cgh.parallel_for<down_dpas_kernel<AddResidual>>(
                sycl::nd_range<2>(sycl::range<2>(pairs, splits), sycl::range<2>(1, splits)),
                [=](sycl::nd_item<2> item) [[intel::sycl_explicit_simd]] {
            esimd::slm_init<slm_floats*sizeof(float)>();
            const int pair = int(item.get_group(0));
            const int split = int(item.get_local_id(1));
            const int tile0 = pair*joint;
            esimd::simd<float, M*joint*16> accum(0.0f);
            const auto * scales = reinterpret_cast<const sycl::half *>(weights + quant_bytes);
            for (int block = split; block < kb; block += splits) {
                esimd::simd<uint32_t, M*8> av;
                av.copy_from(reinterpret_cast<const uint32_t *>(activations) + size_t(block)*M*8);
                for (int j = 0; j < joint; ++j) {
                    const int tile = tile0 + j;
                    if (tile >= nt) {
                        continue;
                    }
                    esimd::simd<uint32_t, 64> bv;
                    bv.copy_from(reinterpret_cast<const uint32_t *>(weights) +
                                 (size_t(block)*nt + tile)*64);
                    auto dot = xmx::dpas<8, M, int32_t, uint32_t, uint32_t,
                            xmx::dpas_argument_type::s4,
                            xmx::dpas_argument_type::s8>(bv, av);
                    esimd::simd<sycl::half, 16> wh;
                    wh.copy_from(scales + size_t(block)*N + tile*16);
                    const auto wf = esimd::convert<float>(wh);
                    for (int row = 0; row < M; ++row) {
                        const esimd::simd<int32_t, 16> di = dot.template select<16, 1>(row*16);
                        const auto & am = meta[block*M + row];
                        accum.template select<16, 1>((j*M + row)*16) +=
                                (esimd::convert<float>(di)*am.d + am.correction)*wf;
                    }
                }
            }
            for (int j = 0; j < joint; ++j) {
                for (int row = 0; row < M; ++row) {
                    const uint32_t offset = uint32_t(
                            (((split*joint + j)*M + row)*16)*sizeof(float));
                    esimd::slm_block_store<float, 16>(
                            offset, accum.template select<16, 1>((j*M + row)*16));
                }
            }
            esimd::barrier();
            if (split == 0) {
                for (int j = 0; j < joint; ++j) {
                    const int tile = tile0 + j;
                    if (tile >= nt) {
                        continue;
                    }
                    for (int row = 0; row < M; ++row) {
                        esimd::simd<float, 16> sum(0.0f);
#pragma unroll
                        for (int partial = 0; partial < splits; ++partial) {
                            const uint32_t offset = uint32_t(
                                    (((partial*joint + j)*M + row)*16)*sizeof(float));
                            sum += esimd::slm_block_load<float, 16>(offset);
                        }
                        if constexpr (AddResidual) {
                            esimd::simd<float, 16> rv;
                            rv.copy_from(residual + size_t(row)*N + tile*16);
                            sum += rv;
                        }
                        sum.copy_to(output + size_t(row)*N + tile*16);
                    }
                }
            }
        });
    });
}

static sycl::event residual_add(
        sycl::queue & queue, float * output, const float * residual) {
    constexpr size_t count = size_t(M)*N;
    constexpr size_t local = 256;
    return queue.submit([&](sycl::handler & cgh) {
        cgh.parallel_for<residual_add_kernel>(
                sycl::nd_range<1>(((count + local - 1)/local)*local, local),
                [=](sycl::nd_item<1> item) {
            const size_t index = item.get_global_linear_id();
            if (index < count) {
                output[index] += residual[index];
            }
        });
    });
}

int main(int argc, char ** argv) {
    const int iterations = argc > 1 ? std::max(5, std::atoi(argv[1])) : 50;
    sycl::queue queue{sycl::gpu_selector_v, sycl::property_list{
            sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::cout << "device=" << queue.get_device().get_info<sycl::info::device::name>()
              << " M=" << M << " K=" << K << " N=" << N
              << " iterations=" << iterations << '\n';

    constexpr int kb = K/QK;
    constexpr int nt = N/16;
    constexpr size_t quant_bytes = size_t(K)*N/2;
    constexpr size_t weight_bytes = quant_bytes + size_t(kb)*N*sizeof(sycl::half);
    constexpr size_t canonical_bytes = size_t(M)*(K + kb*4);
    constexpr size_t soa_bytes = size_t(M)*K + size_t(M)*kb*sizeof(q8_meta);

    std::mt19937 rng(0xb70f0510);
    std::uniform_real_distribution<float> activation(-3.0f, 3.0f);
    std::uniform_real_distribution<float> residual_value(-0.5f, 0.5f);
    std::uniform_real_distribution<float> scale_value(0.0005f, 0.08f);
    std::uniform_int_distribution<int> signed_q4(-8, 7);
    std::vector<float> gate(size_t(M)*K), up(gate.size()), residual(size_t(M)*N);
    for (float & value : gate) value = activation(rng);
    for (float & value : up) value = activation(rng);
    for (float & value : residual) value = residual_value(rng);
    std::vector<uint8_t> packed(weight_bytes, 0);
    auto * scales = reinterpret_cast<sycl::half *>(packed.data() + quant_bytes);
    for (int block = 0; block < kb; ++block) {
        for (int tile = 0; tile < nt; ++tile) {
            for (int lane = 0; lane < 16; ++lane) {
                scales[size_t(block)*N + tile*16 + lane] = sycl::half(scale_value(rng));
                for (int ki = 0; ki < QK; ++ki) {
                    const uint8_t nibble = uint8_t(signed_q4(rng)) & 0x0f;
                    const size_t index = ((((size_t(block)*nt + tile)*4 + ki/8)*16 + lane)*8 + ki%8);
                    packed[index/2] |= nibble << (4*(index & 1));
                }
            }
        }
    }

    auto * d_gate = sycl::malloc_device<float>(gate.size(), queue);
    auto * d_up = sycl::malloc_device<float>(up.size(), queue);
    auto * d_residual = sycl::malloc_device<float>(residual.size(), queue);
    auto * d_swiglu = sycl::malloc_device<float>(gate.size(), queue);
    auto * d_canonical = sycl::malloc_device<int8_t>(canonical_bytes, queue);
    auto * d_soa_baseline = sycl::malloc_device<int8_t>(soa_bytes, queue);
    auto * d_soa_direct = sycl::malloc_device<int8_t>(soa_bytes, queue);
    auto * d_soa_fused = sycl::malloc_device<int8_t>(soa_bytes, queue);
    auto * d_weights = sycl::malloc_device<uint8_t>(packed.size(), queue);
    auto * d_output_baseline = sycl::malloc_device<float>(residual.size(), queue);
    auto * d_output_direct = sycl::malloc_device<float>(residual.size(), queue);
    auto * d_output_fused = sycl::malloc_device<float>(residual.size(), queue);
    if (!d_gate || !d_up || !d_residual || !d_swiglu || !d_canonical ||
            !d_soa_baseline || !d_soa_direct || !d_soa_fused || !d_weights ||
            !d_output_baseline || !d_output_direct || !d_output_fused) {
        std::cerr << "device allocation failed\n";
        return 2;
    }
    queue.memcpy(d_gate, gate.data(), gate.size()*sizeof(float));
    queue.memcpy(d_up, up.data(), up.size()*sizeof(float));
    queue.memcpy(d_residual, residual.data(), residual.size()*sizeof(float));
    queue.memcpy(d_weights, packed.data(), packed.size()).wait();

    auto run_baseline = [&]() {
        const auto e0 = swiglu_store(queue, d_gate, d_up, d_swiglu);
        const auto e1 = canonical_quant(queue, d_swiglu, d_canonical);
        const auto e2 = canonical_repack(queue, d_canonical, d_soa_baseline);
        const auto e3 = down_dpas<false>(
                queue, d_weights, d_soa_baseline, d_residual, d_output_baseline);
        const auto e4 = residual_add(queue, d_output_baseline, d_residual);
        return std::array<sycl::event, 5>{e0, e1, e2, e3, e4};
    };
    auto run_fused = [&]() {
        const auto e0 = fused_swiglu_quant(queue, d_gate, d_up, d_soa_fused);
        const auto e1 = down_dpas<true>(
                queue, d_weights, d_soa_fused, d_residual, d_output_fused);
        return std::array<sycl::event, 2>{e0, e1};
    };
    auto run_direct = [&]() {
        const auto e0 = swiglu_store(queue, d_gate, d_up, d_swiglu);
        const auto e1 = direct_quant(queue, d_swiglu, d_soa_direct);
        const auto e2 = down_dpas<true>(
                queue, d_weights, d_soa_direct, d_residual, d_output_direct);
        return std::array<sycl::event, 3>{e0, e1, e2};
    };

    run_baseline().back().wait_and_throw();
    run_direct().back().wait_and_throw();
    run_fused().back().wait_and_throw();
    std::vector<int8_t> soa_baseline(soa_bytes), soa_direct(soa_bytes), soa_fused(soa_bytes);
    std::vector<float> output_baseline(residual.size()), output_direct(residual.size()),
            output_fused(residual.size());
    queue.memcpy(soa_baseline.data(), d_soa_baseline, soa_bytes);
    queue.memcpy(soa_direct.data(), d_soa_direct, soa_bytes);
    queue.memcpy(soa_fused.data(), d_soa_fused, soa_bytes);
    queue.memcpy(output_baseline.data(), d_output_baseline, output_baseline.size()*sizeof(float));
    queue.memcpy(output_direct.data(), d_output_direct, output_direct.size()*sizeof(float));
    queue.memcpy(output_fused.data(), d_output_fused, output_fused.size()*sizeof(float)).wait();

    size_t direct_soa_differences = 0;
    size_t fused_soa_differences = 0;
    size_t direct_q_differences = 0;
    size_t fused_q_differences = 0;
    for (size_t i = 0; i < soa_bytes; ++i) {
        direct_soa_differences += soa_baseline[i] != soa_direct[i];
        fused_soa_differences += soa_baseline[i] != soa_fused[i];
        if (i < size_t(M)*K) {
            direct_q_differences += soa_baseline[i] != soa_direct[i];
            fused_q_differences += soa_baseline[i] != soa_fused[i];
        }
    }
    const auto * baseline_meta = reinterpret_cast<const q8_meta *>(
            soa_baseline.data() + size_t(M)*K);
    const auto * direct_meta = reinterpret_cast<const q8_meta *>(
            soa_direct.data() + size_t(M)*K);
    size_t meta_d_bit_differences = 0;
    size_t meta_correction_bit_differences = 0;
    float meta_d_max_abs = 0.0f;
    float meta_correction_max_abs = 0.0f;
    for (size_t i = 0; i < size_t(M)*kb; ++i) {
        uint32_t bd = 0, dd = 0, bc = 0, dc = 0;
        std::memcpy(&bd, &baseline_meta[i].d, sizeof(bd));
        std::memcpy(&dd, &direct_meta[i].d, sizeof(dd));
        std::memcpy(&bc, &baseline_meta[i].correction, sizeof(bc));
        std::memcpy(&dc, &direct_meta[i].correction, sizeof(dc));
        meta_d_bit_differences += bd != dd;
        meta_correction_bit_differences += bc != dc;
        meta_d_max_abs = std::max(meta_d_max_abs,
                std::fabs(baseline_meta[i].d - direct_meta[i].d));
        meta_correction_max_abs = std::max(meta_correction_max_abs,
                std::fabs(baseline_meta[i].correction - direct_meta[i].correction));
    }
    size_t direct_output_bit_differences = 0;
    size_t fused_output_bit_differences = 0;
    float direct_max_abs = 0.0f;
    float fused_max_abs = 0.0f;
    double direct_mse = 0.0;
    double fused_mse = 0.0;
    for (size_t i = 0; i < output_baseline.size(); ++i) {
        uint32_t a = 0, b = 0, c = 0;
        std::memcpy(&a, &output_baseline[i], sizeof(a));
        std::memcpy(&b, &output_direct[i], sizeof(b));
        std::memcpy(&c, &output_fused[i], sizeof(c));
        direct_output_bit_differences += a != b;
        fused_output_bit_differences += a != c;
        const float direct_delta = std::fabs(output_baseline[i] - output_direct[i]);
        const float fused_delta = std::fabs(output_baseline[i] - output_fused[i]);
        direct_max_abs = std::max(direct_max_abs, direct_delta);
        fused_max_abs = std::max(fused_max_abs, fused_delta);
        direct_mse += double(direct_delta)*direct_delta;
        fused_mse += double(fused_delta)*fused_delta;
    }

    std::vector<double> baseline_wall, direct_wall, fused_wall;
    std::array<std::vector<double>, 5> baseline_events;
    std::array<std::vector<double>, 3> direct_events;
    std::array<std::vector<double>, 2> fused_events;
    for (int iteration = 0; iteration < iterations; ++iteration) {
        auto begin = std::chrono::steady_clock::now();
        auto baseline = run_baseline();
        baseline.back().wait_and_throw();
        auto end = std::chrono::steady_clock::now();
        baseline_wall.push_back(std::chrono::duration<double, std::micro>(end - begin).count());
        for (size_t i = 0; i < baseline.size(); ++i) baseline_events[i].push_back(event_us(baseline[i]));

        begin = std::chrono::steady_clock::now();
        auto direct = run_direct();
        direct.back().wait_and_throw();
        end = std::chrono::steady_clock::now();
        direct_wall.push_back(std::chrono::duration<double, std::micro>(end - begin).count());
        for (size_t i = 0; i < direct.size(); ++i) direct_events[i].push_back(event_us(direct[i]));

        begin = std::chrono::steady_clock::now();
        auto fused = run_fused();
        fused.back().wait_and_throw();
        end = std::chrono::steady_clock::now();
        fused_wall.push_back(std::chrono::duration<double, std::micro>(end - begin).count());
        for (size_t i = 0; i < fused.size(); ++i) fused_events[i].push_back(event_us(fused[i]));
    }

    const double baseline_median = median(baseline_wall);
    const double direct_median = median(direct_wall);
    const double fused_median = median(fused_wall);
    std::cout << std::fixed << std::setprecision(3)
              << "correctness direct_soa_byte_differences=" << direct_soa_differences
              << " direct_q_byte_differences=" << direct_q_differences
              << " direct_output_bit_differences=" << direct_output_bit_differences
              << " direct_max_abs=" << direct_max_abs
              << " direct_rms=" << std::sqrt(direct_mse/output_baseline.size()) << '\n'
              << "correctness direct_meta_d_bit_differences=" << meta_d_bit_differences
              << " direct_meta_correction_bit_differences=" << meta_correction_bit_differences
              << " direct_meta_d_max_abs=" << meta_d_max_abs
              << " direct_meta_correction_max_abs=" << meta_correction_max_abs << '\n'
              << "diagnostic first_meta baseline_d=" << baseline_meta[0].d
              << " direct_d=" << direct_meta[0].d
              << " baseline_correction=" << baseline_meta[0].correction
              << " direct_correction=" << direct_meta[0].correction << '\n'
              << "correctness fused_soa_byte_differences=" << fused_soa_differences
              << " fused_q_byte_differences=" << fused_q_differences
              << " fused_output_bit_differences=" << fused_output_bit_differences
              << " fused_max_abs=" << fused_max_abs
              << " fused_rms=" << std::sqrt(fused_mse/output_baseline.size()) << '\n'
              << "baseline_event_us swiglu=" << median(baseline_events[0])
              << " canonical_quant=" << median(baseline_events[1])
              << " repack=" << median(baseline_events[2])
              << " down_dpas=" << median(baseline_events[3])
              << " residual=" << median(baseline_events[4]) << '\n'
              << "direct_event_us swiglu=" << median(direct_events[0])
              << " q8_soa=" << median(direct_events[1])
              << " down_dpas_residual=" << median(direct_events[2]) << '\n'
              << "fused_event_us swiglu_q8_soa=" << median(fused_events[0])
              << " down_dpas_residual=" << median(fused_events[1]) << '\n'
              << "boundary_wall_us baseline=" << baseline_median
              << " direct=" << direct_median
              << " direct_saving=" << baseline_median - direct_median
              << " direct_speedup=" << baseline_median/direct_median << 'x'
              << " fused=" << fused_median
              << " fused_saving=" << baseline_median - fused_median
              << " fused_speedup=" << baseline_median/fused_median << 'x' << '\n';

    for (void * pointer : {static_cast<void *>(d_gate), static_cast<void *>(d_up),
                           static_cast<void *>(d_residual), static_cast<void *>(d_swiglu),
                           static_cast<void *>(d_canonical), static_cast<void *>(d_soa_baseline),
                           static_cast<void *>(d_soa_direct), static_cast<void *>(d_soa_fused),
                           static_cast<void *>(d_weights), static_cast<void *>(d_output_baseline),
                           static_cast<void *>(d_output_direct), static_cast<void *>(d_output_fused)}) {
        sycl::free(pointer, queue);
    }
    return direct_soa_differences == 0 && direct_output_bit_differences == 0 ? 0 : 3;
}
