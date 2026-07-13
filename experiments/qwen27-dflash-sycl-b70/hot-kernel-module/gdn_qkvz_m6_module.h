#ifndef Q27_GDN_QKVZ_M6_MODULE_H
#define Q27_GDN_QKVZ_M6_MODULE_H

#include <sycl/sycl.hpp>

#include <cstddef>

struct q27_gdn_qkvz_m6_workspace {
    static constexpr int rows = 6;
    static constexpr int k = 5120;
    static constexpr int n_qkv = 10240;
    static constexpr int n_z = 6144;
    static constexpr size_t activation_quant_bytes = size_t(rows) * k;
    static constexpr size_t activation_meta_bytes =
        size_t(rows) * (k / 32) * 2 * sizeof(float);
    static constexpr size_t bytes = activation_quant_bytes + activation_meta_bytes;
    static constexpr size_t alignment = 8;
    static constexpr size_t qkv_pack_bytes =
        size_t(k) * n_qkv / 2 + size_t(k / 32) * n_qkv * sizeof(sycl::half);
    static constexpr size_t z_pack_bytes =
        size_t(k) * n_z / 2 + size_t(k / 32) * n_z * sizeof(sycl::half);
};

void q27_gdn_qkvz_m6_submit(
    sycl::queue &queue,
    const void *packed_qkv,
    const void *packed_z,
    const float *src,
    float *dst_qkv,
    float *dst_z,
    void *workspace);

#endif
