#ifndef Q27_Q5K_GDN_OUT_M6_MODULE_H
#define Q27_Q5K_GDN_OUT_M6_MODULE_H

#include <sycl/sycl.hpp>

#include <cstddef>

struct q27_q5k_gdn_out_m6_workspace {
    static constexpr int rows = 6;
    static constexpr int k = 6144;
    static constexpr int n = 5120;
    static constexpr int qk = 32;
    static constexpr int super_qk = 256;
    static constexpr size_t activation_quant_bytes = size_t(rows) * k;
    static constexpr size_t activation_meta_bytes =
        size_t(rows) * (k / qk) * (sizeof(float) + sizeof(int32_t));
    static constexpr size_t bytes = activation_quant_bytes + activation_meta_bytes;
    static constexpr size_t alignment = 8;
    static constexpr size_t quant_bytes = size_t(k) * n;
    static constexpr size_t scale_min_bytes = size_t(k / qk) * n * 2;
    static constexpr size_t dm_bytes = size_t(k / super_qk) * n * 2 * sizeof(uint16_t);
    static constexpr size_t pack_bytes = quant_bytes + scale_min_bytes + dm_bytes;
};

void q27_q5k_gdn_out_m6_submit(
    sycl::queue &queue,
    const void *packed_weights,
    const float *src,
    float *dst,
    void *workspace);

#endif
