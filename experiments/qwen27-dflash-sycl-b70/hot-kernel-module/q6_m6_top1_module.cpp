#include "q6_m6_top1_module.h"

#include <sycl/sycl.hpp>

#include <climits>
#include <cmath>
#include <cstddef>
#include <cstdint>

namespace {

class q27_q6_m6_top1_quant_kernel;
class q27_q6_m6_top1_dot_kernel;
class q27_q6_m6_top1_reduce_kernel;

struct top1_pair {
    float value;
    int32_t id;
};

static_assert(sizeof(top1_pair) == 8);
static_assert(q27_q6_m6_top1_workspace::bytes == 337600);

template <typename T>
sycl::vec<T, 4> extract_i8x4(T value) {
    return sycl::vec<T, 1>(value)
        .template as<sycl::vec<int8_t, 4>>()
        .template convert<T>();
}

inline int dp4a_i8(int a, int b, int c) {
    const auto va = extract_i8x4(a);
    const auto vb = extract_i8x4(b);
    return c + va[0] * vb[0] + va[1] * vb[1] + va[2] * vb[2] + va[3] * vb[3];
}

void quantize(sycl::queue &queue, const float *src, int8_t *quants, sycl::half *scales) {
    constexpr int rows = q27_q6_m6_top1_workspace::rows;
    constexpr int k = q27_q6_m6_top1_workspace::k;
    constexpr int lanes = 32;
    constexpr int blocks = k / 32;
    queue.submit([&](sycl::handler &handler) {
        handler.parallel_for<q27_q6_m6_top1_quant_kernel>(
            sycl::nd_range<1>(size_t(rows) * blocks * lanes, lanes),
            [=](sycl::nd_item<1> item) [[sycl::reqd_sub_group_size(lanes)]] {
                const int block = int(item.get_group(0));
                const int row = block / blocks;
                const int kb = block % blocks;
                const int lane = int(item.get_local_id(0));
                const float value = src[size_t(row) * k + kb * 32 + lane];
                const auto subgroup = item.get_sub_group();
                const float amax = sycl::reduce_over_group(
                    subgroup, sycl::fabs(value), sycl::maximum<float>());
                const float scale = amax == 0.0f ? 0.0f : amax / 127.0f;
                quants[size_t(row) * k + kb * 32 + lane] =
                    scale == 0.0f ? int8_t(0) : int8_t(sycl::round(value / scale));
                if (lane == 0) {
                    scales[size_t(row) * blocks + kb] = sycl::half(scale);
                }
            });
    });
}

void dot(
        sycl::queue &queue,
        const int8_t *weight_quants,
        const int8_t *weight_scales,
        const uint16_t *weight_d,
        const int8_t *activation_quants,
        const sycl::half *activation_scales,
        top1_pair *partial) {
    constexpr int rows = q27_q6_m6_top1_workspace::rows;
    constexpr int k = q27_q6_m6_top1_workspace::k;
    constexpr int n = q27_q6_m6_top1_workspace::n;
    constexpr int groups = q27_q6_m6_top1_workspace::groups;
    constexpr int lanes = 32;
    constexpr int subgroups_per_wg = 32;
    constexpr int qk = 256;
    queue.submit([&](sycl::handler &handler) {
        sycl::local_accessor<float, 1> local(rows * subgroups_per_wg, handler);
        handler.parallel_for<q27_q6_m6_top1_dot_kernel>(
            sycl::nd_range<1>(size_t(groups) * subgroups_per_wg * lanes,
                              subgroups_per_wg * lanes),
            [=](sycl::nd_item<1> item) [[sycl::reqd_sub_group_size(lanes)]] {
                const int lane = int(item.get_local_id(0)) & (lanes - 1);
                const int subgroup_index = int(item.get_local_id(0)) / lanes;
                const int output_id = int(item.get_group(0)) * subgroups_per_wg + subgroup_index;
                const auto subgroup = item.get_sub_group();
                float accum[rows] = {};

                if (output_id < n) {
                    for (int ib = 0; ib < k / qk; ++ib) {
                        const sycl::half dh = sycl::bit_cast<sycl::half>(
                            weight_d[size_t(output_id) * (k / qk) + ib]);
                        const float sw = float(dh) * float(
                            weight_scales[size_t(output_id) * (k / 16) + ib * 16 + lane / 2]);
                        const int k0 = ib * qk + lane * 8;
                        const int w0 = *reinterpret_cast<const int *>(
                            weight_quants + size_t(output_id) * k + k0);
                        const int w1 = *reinterpret_cast<const int *>(
                            weight_quants + size_t(output_id) * k + k0 + 4);
#pragma unroll
                        for (int row = 0; row < rows; ++row) {
                            const int x0 = *reinterpret_cast<const int *>(
                                activation_quants + size_t(row) * k + k0);
                            const int x1 = *reinterpret_cast<const int *>(
                                activation_quants + size_t(row) * k + k0 + 4);
                            const int value = dp4a_i8(w0, x0, 0) + dp4a_i8(w1, x1, 0);
                            accum[row] += float(value) * sw * float(
                                activation_scales[size_t(row) * (k / 32) + ib * 8 + lane / 4]);
                        }
                    }
                }

#pragma unroll
                for (int row = 0; row < rows; ++row) {
                    const float sum = sycl::reduce_over_group(subgroup, accum[row], sycl::plus<float>());
                    if (lane == 0) {
                        local[subgroup_index * rows + row] = output_id < n ? sum : -INFINITY;
                    }
                }
                item.barrier(sycl::access::fence_space::local_space);
                if (int(item.get_local_id(0)) < rows) {
                    const int row = int(item.get_local_id(0));
                    top1_pair best{-INFINITY, int32_t(item.get_group(0) * subgroups_per_wg)};
                    for (int subgroup_id = 0; subgroup_id < subgroups_per_wg; ++subgroup_id) {
                        const int id = int(item.get_group(0)) * subgroups_per_wg + subgroup_id;
                        const float value = local[subgroup_id * rows + row];
                        if (id < n && (value > best.value ||
                                (value == best.value && id < best.id))) {
                            best = {value, id};
                        }
                    }
                    partial[size_t(row) * groups + item.get_group(0)] = best;
                }
            });
    });
}

void reduce(sycl::queue &queue, const top1_pair *partial, int32_t *result) {
    constexpr int rows = q27_q6_m6_top1_workspace::rows;
    constexpr int groups = q27_q6_m6_top1_workspace::groups;
    constexpr int wg = 256;
    queue.submit([&](sycl::handler &handler) {
        sycl::local_accessor<float, 1> local_values(wg, handler);
        sycl::local_accessor<int32_t, 1> local_ids(wg, handler);
        handler.parallel_for<q27_q6_m6_top1_reduce_kernel>(
            sycl::nd_range<1>(rows * wg, wg), [=](sycl::nd_item<1> item) {
                const int row = int(item.get_group(0));
                const int lane = int(item.get_local_id(0));
                top1_pair best{-INFINITY, INT32_MAX};
                for (int group = lane; group < groups; group += wg) {
                    const auto candidate = partial[size_t(row) * groups + group];
                    if (candidate.value > best.value ||
                            (candidate.value == best.value && candidate.id < best.id)) {
                        best = candidate;
                    }
                }
                local_values[lane] = best.value;
                local_ids[lane] = best.id;
                item.barrier(sycl::access::fence_space::local_space);
                for (int step = wg / 2; step > 0; step /= 2) {
                    if (lane < step && (local_values[lane + step] > local_values[lane] ||
                            (local_values[lane + step] == local_values[lane] &&
                             local_ids[lane + step] < local_ids[lane]))) {
                        local_values[lane] = local_values[lane + step];
                        local_ids[lane] = local_ids[lane + step];
                    }
                    item.barrier(sycl::access::fence_space::local_space);
                }
                if (lane == 0) {
                    result[row] = local_ids[0];
                }
            });
    });
}

} // namespace

void q27_q6_m6_top1_submit(
        sycl::queue &queue,
        const void *packed_weights,
        const float *src,
        int32_t *dst,
        void *workspace) {
    constexpr int k = q27_q6_m6_top1_workspace::k;
    constexpr int n = q27_q6_m6_top1_workspace::n;
    constexpr size_t quant_bytes = size_t(k) * n;
    constexpr size_t scale_bytes = size_t(k / 16) * n;

    auto *scratch = static_cast<int8_t *>(workspace);
    auto *activation_quants = scratch;
    auto *activation_scales = reinterpret_cast<sycl::half *>(
        scratch + q27_q6_m6_top1_workspace::activation_quant_bytes);
    auto *partial = reinterpret_cast<top1_pair *>(
        scratch + q27_q6_m6_top1_workspace::activation_quant_bytes +
        q27_q6_m6_top1_workspace::activation_scale_bytes);

    const auto *weight_quants = static_cast<const int8_t *>(packed_weights);
    const auto *weight_scales = weight_quants + quant_bytes;
    const auto *weight_d = reinterpret_cast<const uint16_t *>(weight_scales + scale_bytes);

    quantize(queue, src, activation_quants, activation_scales);
    dot(queue, weight_quants, weight_scales, weight_d,
        activation_quants, activation_scales, partial);
    reduce(queue, partial, dst);
}
