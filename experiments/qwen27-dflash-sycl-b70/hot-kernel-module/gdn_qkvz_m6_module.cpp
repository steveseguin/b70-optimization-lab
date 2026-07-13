#include "gdn_qkvz_m6_module.h"

#include <sycl/ext/intel/esimd.hpp>

#include <cstddef>
#include <cstdint>

namespace esimd = sycl::ext::intel::esimd;
namespace xmx = sycl::ext::intel::esimd::xmx;

namespace {

class q27_gdn_qkvz_m6_quant_kernel;
class q27_gdn_qkvz_m6_joint_kernel;

struct q8_meta {
    float d;
    float correction;
};

static_assert(sizeof(q8_meta) == 8);
static_assert(q27_gdn_qkvz_m6_workspace::bytes == 38400);
static_assert(q27_gdn_qkvz_m6_workspace::qkv_pack_bytes == 29491200);
static_assert(q27_gdn_qkvz_m6_workspace::z_pack_bytes == 17694720);

void quantize(sycl::queue &queue, const float *src, int8_t *dst) {
    constexpr int m = q27_gdn_qkvz_m6_workspace::rows;
    constexpr int k = q27_gdn_qkvz_m6_workspace::k;
    constexpr int lanes = 16;
    constexpr int values_per_lane = 32 / lanes;
    constexpr int kb = k / 32;
    queue.submit([&](sycl::handler &handler) {
        handler.parallel_for<q27_gdn_qkvz_m6_quant_kernel>(
            sycl::nd_range<1>(m * kb * lanes, lanes),
            [=](sycl::nd_item<1> item) [[sycl::reqd_sub_group_size(lanes)]] {
                const int block = int(item.get_group(0));
                const int row = block / kb;
                const int ki = block % kb;
                const int lane = int(item.get_local_id(0));
                float values[values_per_lane];
                float sum = 0.0f;
                float amax = 0.0f;
#pragma unroll
                for (int j = 0; j < values_per_lane; ++j) {
                    const int element = lane * values_per_lane + j;
                    values[j] = src[size_t(row) * k + ki * 32 + element];
                    sum += values[j];
                    amax = sycl::fmax(amax, sycl::fabs(values[j]));
                }
                const auto subgroup = item.get_sub_group();
                amax = sycl::reduce_over_group(subgroup, amax, sycl::maximum<float>());
                sum = sycl::reduce_over_group(subgroup, sum, sycl::plus<float>());
                const float quant_d = amax != 0.0f ? amax / 127.0f : 1.0f;
                int lane_qsum = 0;
#pragma unroll
                for (int j = 0; j < values_per_lane; ++j) {
                    const int element = lane * values_per_lane + j;
                    const int q = int(sycl::round(values[j] / quant_d));
                    dst[(size_t(ki) * m + row) * 32 + element] = int8_t(q);
                    lane_qsum += q;
                }
                const int qsum = sycl::reduce_over_group(subgroup, lane_qsum, sycl::plus<int>());
                if (lane == 0) {
                    const float hd = float(sycl::half(amax != 0.0f ? quant_d : 0.0f));
                    const float hs = float(sycl::half(sum));
                    auto *meta = reinterpret_cast<q8_meta *>(dst + size_t(k) * m);
                    meta[ki * m + row] = {hd, 8.0f * (qsum * hd - hs)};
                }
            });
    });
}

void project_both(
        sycl::queue &queue,
        const uint8_t *weights_qkv,
        const uint8_t *weights_z,
        const int8_t *activations,
        float *dst_qkv,
        float *dst_z) {
    constexpr int m = q27_gdn_qkvz_m6_workspace::rows;
    constexpr int k = q27_gdn_qkvz_m6_workspace::k;
    constexpr int n_qkv = q27_gdn_qkvz_m6_workspace::n_qkv;
    constexpr int n_z = q27_gdn_qkvz_m6_workspace::n_z;
    constexpr int splits = 8;
    constexpr int joint = 2;
    constexpr int slm_floats = splits * joint * m * 16;
    constexpr int kb = k / 32;
    constexpr int qkv_tiles = n_qkv / 16;
    constexpr int z_tiles = n_z / 16;
    constexpr int qkv_pairs = (qkv_tiles + joint - 1) / joint;
    constexpr int z_pairs = (z_tiles + joint - 1) / joint;
    constexpr int total_pairs = qkv_pairs + z_pairs;
    const auto *activation_meta = reinterpret_cast<const q8_meta *>(
        activations + size_t(k) * m);

    queue.submit([&](sycl::handler &handler) {
        handler.parallel_for<q27_gdn_qkvz_m6_joint_kernel>(
            sycl::nd_range<2>(sycl::range<2>(total_pairs, splits), sycl::range<2>(1, splits)),
            [=](sycl::nd_item<2> item) [[intel::sycl_explicit_simd]] {
                esimd::slm_init<slm_floats * sizeof(float)>();
                const int global_pair = int(item.get_group(0));
                const bool is_z = global_pair >= qkv_pairs;
                const int pair = is_z ? global_pair - qkv_pairs : global_pair;
                const int split = int(item.get_local_id(1));
                const int tile0 = pair * joint;
                const int n = is_z ? n_z : n_qkv;
                const int nt = is_z ? z_tiles : qkv_tiles;
                const uint8_t *weights = is_z ? weights_z : weights_qkv;
                float *dst = is_z ? dst_z : dst_qkv;
                const size_t quant_bytes = size_t(k) * n / 2;
                const auto *weight_scales = reinterpret_cast<const sycl::half *>(
                    weights + quant_bytes);
                esimd::simd<float, m * joint * 16> accum(0.0f);

                // Preserve the production candidate's strided eight-way K reduction order.
                for (int block = split; block < kb; block += splits) {
                    esimd::simd<uint32_t, m * 8> av;
                    av.copy_from(reinterpret_cast<const uint32_t *>(activations) + size_t(block) * m * 8);
                    for (int j = 0; j < joint; ++j) {
                        const int tile = tile0 + j;
                        if (tile >= nt) {
                            continue;
                        }
                        esimd::simd<uint32_t, 64> bv;
                        bv.copy_from(reinterpret_cast<const uint32_t *>(weights) +
                                     (size_t(block) * nt + tile) * 64);
                        esimd::simd<int32_t, m * 16> dot =
                            xmx::dpas<8, m, int32_t, uint32_t, uint32_t,
                                xmx::dpas_argument_type::s4,
                                xmx::dpas_argument_type::s8>(bv, av);
                        esimd::simd<sycl::half, 16> wh;
                        wh.copy_from(weight_scales + size_t(block) * n + tile * 16);
                        const auto wf = esimd::convert<float>(wh);
                        for (int row = 0; row < m; ++row) {
                            esimd::simd<int32_t, 16> di =
                                dot.template select<16, 1>(row * 16);
                            const auto &meta = activation_meta[block * m + row];
                            accum.template select<16, 1>((j * m + row) * 16) +=
                                (esimd::convert<float>(di) * meta.d + meta.correction) * wf;
                        }
                    }
                }

                for (int j = 0; j < joint; ++j) {
                    for (int row = 0; row < m; ++row) {
                        const uint32_t offset = uint32_t(
                            (((split * joint + j) * m + row) * 16) * sizeof(float));
                        esimd::slm_block_store<float, 16>(
                            offset, accum.template select<16, 1>((j * m + row) * 16));
                    }
                }
                esimd::barrier();
                if (split == 0) {
                    for (int j = 0; j < joint; ++j) {
                        const int tile = tile0 + j;
                        if (tile >= nt) {
                            continue;
                        }
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

void q27_gdn_qkvz_m6_submit(
        sycl::queue &queue,
        const void *packed_qkv,
        const void *packed_z,
        const float *src,
        float *dst_qkv,
        float *dst_z,
        void *workspace) {
    auto *activations = static_cast<int8_t *>(workspace);
    quantize(queue, src, activations);
    project_both(queue, static_cast<const uint8_t *>(packed_qkv),
                 static_cast<const uint8_t *>(packed_z), activations, dst_qkv, dst_z);
}
