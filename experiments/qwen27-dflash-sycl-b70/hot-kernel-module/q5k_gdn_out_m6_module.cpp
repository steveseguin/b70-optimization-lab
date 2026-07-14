#include "q5k_gdn_out_m6_module.h"

#include <sycl/ext/intel/esimd.hpp>

#include <cstddef>
#include <cstdint>

namespace esimd = sycl::ext::intel::esimd;
namespace xmx = sycl::ext::intel::esimd::xmx;

namespace {

class q27_q5k_gdn_out_m6_quant_kernel;
class q27_q5k_gdn_out_m6_dpas_kernel;

struct q8_meta {
    float d;
    int32_t qsum;
};

static_assert(sizeof(q8_meta) == 8);
static_assert(q27_q5k_gdn_out_m6_workspace::bytes == 46080);
static_assert(q27_q5k_gdn_out_m6_workspace::pack_bytes == 33914880);

void quantize(sycl::queue &queue, const float *src, int8_t *dst) {
    constexpr int m = q27_q5k_gdn_out_m6_workspace::rows;
    constexpr int k = q27_q5k_gdn_out_m6_workspace::k;
    constexpr int kb = k / 32;
    constexpr int lanes = 16;
    queue.submit([&](sycl::handler &handler) {
        handler.parallel_for<q27_q5k_gdn_out_m6_quant_kernel>(
            sycl::nd_range<1>(m * kb * lanes, lanes),
            [=](sycl::nd_item<1> item) [[sycl::reqd_sub_group_size(lanes)]] {
                const int linear = int(item.get_group(0));
                const int row = linear / kb;
                const int block = linear % kb;
                const int lane = int(item.get_local_id(0));
                float values[2];
                float sum = 0.0f;
                float amax = 0.0f;
#pragma unroll
                for (int j = 0; j < 2; ++j) {
                    const int element = lane * 2 + j;
                    values[j] = src[size_t(row) * k + block * 32 + element];
                    sum += values[j];
                    amax = sycl::fmax(amax, sycl::fabs(values[j]));
                }
                const auto subgroup = item.get_sub_group();
                sum = sycl::reduce_over_group(subgroup, sum, sycl::plus<float>());
                amax = sycl::reduce_over_group(subgroup, amax, sycl::maximum<float>());
                const float d = amax == 0.0f ? 1.0f : amax / 127.0f;
                int lane_qsum = 0;
#pragma unroll
                for (int j = 0; j < 2; ++j) {
                    const int element = lane * 2 + j;
                    const int q = int(sycl::round(values[j] / d));
                    dst[(size_t(block) * m + row) * 32 + element] = int8_t(q);
                    lane_qsum += q;
                }
                const int qsum = sycl::reduce_over_group(
                    subgroup, lane_qsum, sycl::plus<int>());
                if (lane == 0) {
                    // BMG AOT can eliminate a local float->half->float round trip.
                    volatile uint16_t d_bits = sycl::bit_cast<uint16_t>(
                        sycl::half(amax == 0.0f ? 0.0f : d));
                    const float rounded_d = float(
                        sycl::bit_cast<sycl::half>(uint16_t(d_bits)));
                    auto *meta = reinterpret_cast<q8_meta *>(dst + size_t(m) * k);
                    meta[block * m + row] = {rounded_d, qsum};
                }
            });
    });
}

void project(
        sycl::queue &queue, const uint8_t *weights, const int8_t *activations,
        float *dst) {
    constexpr int m = q27_q5k_gdn_out_m6_workspace::rows;
    constexpr int k = q27_q5k_gdn_out_m6_workspace::k;
    constexpr int n = q27_q5k_gdn_out_m6_workspace::n;
    constexpr int kb = k / 32;
    constexpr int sb = k / 256;
    constexpr int nt = n / 16;
    constexpr int splits = 8;
    constexpr int joint = 2;
    constexpr int pairs = (nt + joint - 1) / joint;
    constexpr int slm_floats = splits * joint * m * 16;
    constexpr size_t quant_bytes = q27_q5k_gdn_out_m6_workspace::quant_bytes;
    constexpr size_t scale_min_bytes = q27_q5k_gdn_out_m6_workspace::scale_min_bytes;
    const uint16_t *scale_min = reinterpret_cast<const uint16_t *>(weights + quant_bytes);
    const sycl::half2 *dm = reinterpret_cast<const sycl::half2 *>(
        weights + quant_bytes + scale_min_bytes);
    const auto *meta = reinterpret_cast<const q8_meta *>(activations + size_t(m) * k);

    queue.submit([&](sycl::handler &handler) {
        handler.parallel_for<q27_q5k_gdn_out_m6_dpas_kernel>(
            sycl::nd_range<2>(sycl::range<2>(pairs, splits), sycl::range<2>(1, splits)),
            [=](sycl::nd_item<2> item) [[intel::sycl_explicit_simd]] {
                esimd::slm_init<slm_floats * sizeof(float)>();
                const int pair = int(item.get_group(0));
                const int split = int(item.get_local_id(1));
                const int tile0 = pair * joint;
                esimd::simd<float, m * joint * 16> accum(0.0f);

                // One split owns whole 256-value superblocks. This preserves
                // Q5_K's per-superblock scale/min accumulation boundary.
                for (int super = split; super < sb; super += splits) {
                    for (int j = 0; j < joint; ++j) {
                        const int tile = tile0 + j;
                        if (tile >= nt) continue;
                        esimd::simd<sycl::half, 32> dm_half;
                        dm_half.copy_from(reinterpret_cast<const sycl::half *>(dm) +
                            (size_t(super) * n + tile * 16) * 2);
                        esimd::simd<float, 32> dm_float = esimd::convert<float>(dm_half);
                        esimd::simd<float, m * 16> sum_d(0.0f);
                        esimd::simd<float, m * 16> sum_m(0.0f);
                        for (int group = 0; group < 8; ++group) {
                            const int block = super * 8 + group;
                            esimd::simd<uint32_t, m * 8> av;
                            av.copy_from(reinterpret_cast<const uint32_t *>(activations) +
                                size_t(block) * m * 8);
                            esimd::simd<uint32_t, 128> bv;
                            bv.copy_from(reinterpret_cast<const uint32_t *>(weights) +
                                (size_t(block) * nt + tile) * 128);
                            esimd::simd<int32_t, m * 16> dot =
                                xmx::dpas<8, m, int32_t, uint32_t, uint32_t,
                                xmx::dpas_argument_type::s8,
                                xmx::dpas_argument_type::s8>(bv, av);
                            esimd::simd<uint16_t, 16> sm;
                            sm.copy_from(scale_min + size_t(block) * n + tile * 16);
                            esimd::simd<int32_t, 16> sc =
                                esimd::convert<int32_t>(sm & uint16_t(0x00ff));
                            esimd::simd<int32_t, 16> mn =
                                esimd::convert<int32_t>(sm >> 8);
                            for (int row = 0; row < m; ++row) {
                                const auto di = dot.template select<16, 1>(row * 16);
                                const auto &am = meta[block * m + row];
                                sum_d.template select<16, 1>(row * 16) +=
                                    esimd::convert<float>(di * sc) * am.d;
                                sum_m.template select<16, 1>(row * 16) +=
                                    esimd::convert<float>(mn * am.qsum) * am.d;
                            }
                        }
                        for (int row = 0; row < m; ++row) {
                            const auto dall = dm_float.template select<16, 2>(0);
                            const auto dmin = dm_float.template select<16, 2>(1);
                            accum.template select<16, 1>((j * m + row) * 16) +=
                                dall * sum_d.template select<16, 1>(row * 16) -
                                dmin * sum_m.template select<16, 1>(row * 16);
                        }
                    }
                }

                for (int j = 0; j < joint; ++j) {
                    for (int row = 0; row < m; ++row) {
                        const uint32_t offset = uint32_t(
                            (((split * joint + j) * m + row) * 16) * sizeof(float));
                        esimd::slm_block_store<float, 16>(offset,
                            accum.template select<16, 1>((j * m + row) * 16));
                    }
                }
                esimd::barrier();
                if (split == 0) {
                    for (int j = 0; j < joint; ++j) {
                        const int tile = tile0 + j;
                        if (tile >= nt) continue;
                        for (int row = 0; row < m; ++row) {
                            esimd::simd<float, 16> sum(0.0f);
#pragma unroll
                            for (int partial = 0; partial < splits; ++partial) {
                                const uint32_t offset = uint32_t(
                                    (((partial * joint + j) * m + row) * 16) * sizeof(float));
                                sum += esimd::slm_block_load<float, 16>(offset);
                            }
                            sum.copy_to(dst + size_t(row) * n + tile * 16);
                        }
                    }
                }
            });
    });
}

} // namespace

void q27_q5k_gdn_out_m6_submit(
        sycl::queue &queue, const void *packed_weights, const float *src,
        float *dst, void *workspace) {
    auto *activations = static_cast<int8_t *>(workspace);
    quantize(queue, src, activations);
    project(queue, static_cast<const uint8_t *>(packed_weights), activations, dst);
}
