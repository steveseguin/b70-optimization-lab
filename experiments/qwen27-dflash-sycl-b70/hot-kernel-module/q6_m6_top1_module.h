#ifndef Q27_Q6_M6_TOP1_MODULE_H
#define Q27_Q6_M6_TOP1_MODULE_H

#include <sycl/sycl.hpp>

#include <cstddef>
#include <cstdint>

struct q27_q6_m6_top1_workspace {
    static constexpr int rows = 5;
    static constexpr int k = 5120;
    static constexpr int n = 248320;
    static constexpr int groups = (n + 31) / 32;
    static constexpr size_t activation_quant_bytes = size_t(rows) * k;
    static constexpr size_t activation_scale_bytes = size_t(rows) * (k / 32) * sizeof(sycl::half);
    static constexpr size_t partial_bytes = size_t(rows) * groups * 2 * sizeof(uint32_t);
    static constexpr size_t bytes =
        activation_quant_bytes + activation_scale_bytes + partial_bytes;
    static constexpr size_t alignment = 8;
};

void q27_q6_m6_top1_submit(
    sycl::queue &queue,
    const void *packed_weights,
    const float *src,
    int32_t *dst,
    void *workspace);

#endif
