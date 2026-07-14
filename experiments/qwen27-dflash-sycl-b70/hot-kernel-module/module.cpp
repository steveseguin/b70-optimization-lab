#include "q27_xe2_module.h"
#include "gdn_qkvz_m6_module.h"
#include "q6_m6_top1_module.h"
#include "q5k_gdn_out_m6_module.h"

#include <sycl/sycl.hpp>

#include <cstddef>
#include <exception>

#ifndef Q27_XE2_BUILD_ID
#define Q27_XE2_BUILD_ID "development"
#endif

#ifndef Q27_XE2_TOOLCHAIN_ABI
#define Q27_XE2_TOOLCHAIN_ABI "oneapi-2026.0-sycl-cxx17"
#endif

#ifndef Q27_XE2_TARGET_ARCH
#define Q27_XE2_TARGET_ARCH "bmg-g31"
#endif

namespace {

class smoke_axpy_kernel;

int32_t query_workspace(
        uint32_t op,
        uint32_t rows,
        uint32_t cols,
        q27_xe2_workspace_v1 *workspace) {
    if (workspace == nullptr) {
        return Q27_XE2_BAD_ARGUMENT;
    }
    if (op == Q27_XE2_OP_SMOKE_AXPY) {
        workspace->bytes = 0;
        workspace->alignment = 1;
        return Q27_XE2_OK;
    }
    if (op == Q27_XE2_OP_Q6K_M6_TOP1) {
        if (rows != q27_q6_m6_top1_workspace::rows ||
                cols != q27_q6_m6_top1_workspace::n) {
            return Q27_XE2_BAD_SHAPE;
        }
        workspace->bytes = q27_q6_m6_top1_workspace::bytes;
        workspace->alignment = q27_q6_m6_top1_workspace::alignment;
        return Q27_XE2_OK;
    }
    if (op == Q27_XE2_OP_GDN_QKVZ_M6) {
        if (rows != q27_gdn_qkvz_m6_workspace::rows ||
                cols != q27_gdn_qkvz_m6_workspace::n_qkv) {
            return Q27_XE2_BAD_SHAPE;
        }
        workspace->bytes = q27_gdn_qkvz_m6_workspace::bytes;
        workspace->alignment = q27_gdn_qkvz_m6_workspace::alignment;
        return Q27_XE2_OK;
    }
    if (op == Q27_XE2_OP_GDN_QKVZAB_M6) {
        if (rows != q27_gdn_qkvz_m6_workspace::rows ||
                cols != q27_gdn_qkvz_m6_workspace::n_qkv) {
            return Q27_XE2_BAD_SHAPE;
        }
        workspace->bytes = q27_gdn_qkvz_m6_workspace::bytes;
        workspace->alignment = q27_gdn_qkvz_m6_workspace::alignment;
        return Q27_XE2_OK;
    }
    if (op == Q27_XE2_OP_GDN_QKVZAB_GATE_M6) {
        if (rows != q27_gdn_qkvz_m6_workspace::rows ||
                cols != q27_gdn_qkvz_m6_workspace::n_qkv) {
            return Q27_XE2_BAD_SHAPE;
        }
        workspace->bytes = q27_gdn_qkvz_m6_workspace::bytes;
        workspace->alignment = q27_gdn_qkvz_m6_workspace::alignment;
        return Q27_XE2_OK;
    }
    if (op == Q27_XE2_OP_Q5K_GDN_OUT_M6) {
        if (rows != q27_q5k_gdn_out_m6_workspace::rows ||
                cols != q27_q5k_gdn_out_m6_workspace::n) {
            return Q27_XE2_BAD_SHAPE;
        }
        workspace->bytes = q27_q5k_gdn_out_m6_workspace::bytes;
        workspace->alignment = q27_q5k_gdn_out_m6_workspace::alignment;
        return Q27_XE2_OK;
    }
    return Q27_XE2_DECLINED;
}

int32_t launch(const q27_xe2_launch_v1 *args) {
    /* Complete validation before q.submit: all failures below are fallback-safe. */
    if (args == nullptr || args->struct_size < Q27_XE2_LAUNCH_V1_BASE_SIZE) {
        return Q27_XE2_BAD_ABI;
    }
    if ((args->flags & Q27_XE2_QUEUE_IS_IN_ORDER) == 0 || args->queue == nullptr) {
        return Q27_XE2_BAD_ARGUMENT;
    }

    auto *queue = static_cast<sycl::queue *>(args->queue);

    try {
        if (args->op == Q27_XE2_OP_SMOKE_AXPY) {
            if (args->input0 == nullptr || args->output0 == nullptr || args->cols == 0) {
                return Q27_XE2_BAD_ARGUMENT;
            }
            const auto *input = static_cast<const float *>(args->input0);
            auto *output = static_cast<float *>(args->output0);
            const size_t count = args->cols;
            const float alpha = args->scalar0;
            queue->submit([&](sycl::handler &handler) {
                handler.parallel_for<smoke_axpy_kernel>(sycl::range<1>(count), [=](sycl::id<1> index) {
                    output[index] += alpha * input[index];
                });
            });
            return Q27_XE2_OK;
        }
        if (args->op == Q27_XE2_OP_Q6K_M6_TOP1) {
            if (args->input0 == nullptr || args->output0 == nullptr || args->scratch == nullptr ||
                    args->rows != q27_q6_m6_top1_workspace::rows ||
                    args->cols != q27_q6_m6_top1_workspace::n ||
                    args->stride != q27_q6_m6_top1_workspace::k ||
                    args->scratch_bytes < q27_q6_m6_top1_workspace::bytes) {
                return Q27_XE2_BAD_SHAPE;
            }
            if (args->packs == nullptr || args->pack_count != 1) {
                return Q27_XE2_BAD_LAYOUT;
            }
            const q27_xe2_pack_v1 &pack = args->packs[0];
            constexpr uint64_t expected_bytes =
                uint64_t(q27_q6_m6_top1_workspace::k) * q27_q6_m6_top1_workspace::n +
                uint64_t(q27_q6_m6_top1_workspace::k / 16) * q27_q6_m6_top1_workspace::n +
                uint64_t(q27_q6_m6_top1_workspace::k / 256) *
                    q27_q6_m6_top1_workspace::n * sizeof(uint16_t);
            if (pack.device_ptr == nullptr || pack.bytes != expected_bytes ||
                    pack.layout_id != Q27_XE2_LAYOUT_Q6K_M6_TOP1_V1 ||
                    pack.content_tag != Q27_XE2_QWEN36_27B_Q4_MODEL_TAG ||
                    pack.role != Q27_XE2_PACK_TARGET_LM_HEAD) {
                return Q27_XE2_BAD_LAYOUT;
            }
            q27_q6_m6_top1_submit(
                *queue, pack.device_ptr, static_cast<const float *>(args->input0),
                static_cast<int32_t *>(args->output0), args->scratch);
            return Q27_XE2_OK;
        }
        if (args->op == Q27_XE2_OP_GDN_QKVZ_M6) {
            if (args->input0 == nullptr || args->output0 == nullptr ||
                    args->state0 == nullptr || args->scratch == nullptr ||
                    args->rows != q27_gdn_qkvz_m6_workspace::rows ||
                    args->cols != q27_gdn_qkvz_m6_workspace::n_qkv ||
                    args->stride != q27_gdn_qkvz_m6_workspace::k ||
                    args->scratch_bytes < q27_gdn_qkvz_m6_workspace::bytes) {
                return Q27_XE2_BAD_SHAPE;
            }
            if (args->packs == nullptr || args->pack_count != 2) {
                return Q27_XE2_BAD_LAYOUT;
            }
            const q27_xe2_pack_v1 &qkv = args->packs[0];
            const q27_xe2_pack_v1 &z = args->packs[1];
            if (qkv.device_ptr == nullptr ||
                    qkv.bytes != q27_gdn_qkvz_m6_workspace::qkv_pack_bytes ||
                    qkv.layout_id != Q27_XE2_LAYOUT_Q4_0_Q8_1_V1 ||
                    qkv.content_tag != Q27_XE2_QWEN36_27B_Q4_MODEL_TAG ||
                    qkv.role != Q27_XE2_PACK_GDN_QKV ||
                    z.device_ptr == nullptr ||
                    z.bytes != q27_gdn_qkvz_m6_workspace::z_pack_bytes ||
                    z.layout_id != Q27_XE2_LAYOUT_Q4_0_Q8_1_V1 ||
                    z.content_tag != Q27_XE2_QWEN36_27B_Q4_MODEL_TAG ||
                    z.role != Q27_XE2_PACK_GDN_Z) {
                return Q27_XE2_BAD_LAYOUT;
            }
            q27_gdn_qkvz_m6_submit(
                *queue, qkv.device_ptr, z.device_ptr,
                static_cast<const float *>(args->input0),
                static_cast<float *>(args->output0),
                static_cast<float *>(args->state0), args->scratch);
            return Q27_XE2_OK;
        }
        if (args->op == Q27_XE2_OP_GDN_QKVZAB_M6) {
            if (args->struct_size < sizeof(q27_xe2_launch_v1)) {
                return Q27_XE2_BAD_ABI;
            }
            if (args->input0 == nullptr || args->output0 == nullptr ||
                    args->output1 == nullptr || args->output2 == nullptr ||
                    args->output3 == nullptr || args->scratch == nullptr ||
                    args->rows != q27_gdn_qkvz_m6_workspace::rows ||
                    args->cols != q27_gdn_qkvz_m6_workspace::n_qkv ||
                    args->stride != q27_gdn_qkvz_m6_workspace::k ||
                    args->scratch_bytes < q27_gdn_qkvz_m6_workspace::bytes) {
                return Q27_XE2_BAD_SHAPE;
            }
            if (args->packs == nullptr || args->pack_count != 3) {
                return Q27_XE2_BAD_LAYOUT;
            }
            const q27_xe2_pack_v1 &qkv = args->packs[0];
            const q27_xe2_pack_v1 &z = args->packs[1];
            const q27_xe2_pack_v1 &alpha_beta = args->packs[2];
            if (qkv.device_ptr == nullptr ||
                    qkv.bytes != q27_gdn_qkvz_m6_workspace::qkv_pack_bytes ||
                    qkv.layout_id != Q27_XE2_LAYOUT_Q4_0_Q8_1_V1 ||
                    qkv.content_tag != Q27_XE2_QWEN36_27B_Q4_MODEL_TAG ||
                    qkv.role != Q27_XE2_PACK_GDN_QKV ||
                    z.device_ptr == nullptr ||
                    z.bytes != q27_gdn_qkvz_m6_workspace::z_pack_bytes ||
                    z.layout_id != Q27_XE2_LAYOUT_Q4_0_Q8_1_V1 ||
                    z.content_tag != Q27_XE2_QWEN36_27B_Q4_MODEL_TAG ||
                    z.role != Q27_XE2_PACK_GDN_Z ||
                    alpha_beta.device_ptr == nullptr ||
                    alpha_beta.bytes != q27_gdn_qkvz_m6_workspace::alpha_beta_pack_bytes ||
                    alpha_beta.layout_id != Q27_XE2_LAYOUT_F32_GDN_BA_V1 ||
                    alpha_beta.content_tag != Q27_XE2_QWEN36_27B_Q4_MODEL_TAG ||
                    alpha_beta.role != Q27_XE2_PACK_GDN_ALPHA_BETA) {
                return Q27_XE2_BAD_LAYOUT;
            }
            q27_gdn_qkvzab_m6_submit(
                *queue, qkv.device_ptr, z.device_ptr,
                static_cast<const float *>(alpha_beta.device_ptr),
                static_cast<const float *>(args->input0),
                static_cast<float *>(args->output0),
                static_cast<float *>(args->output1),
                static_cast<float *>(args->output2),
                static_cast<float *>(args->output3), args->scratch);
            return Q27_XE2_OK;
        }
        if (args->op == Q27_XE2_OP_GDN_QKVZAB_GATE_M6) {
            if (args->struct_size < sizeof(q27_xe2_launch_v1)) {
                return Q27_XE2_BAD_ABI;
            }
            if (args->input0 == nullptr || args->output0 == nullptr ||
                    args->output1 == nullptr || args->output2 == nullptr ||
                    args->output3 == nullptr || args->scratch == nullptr ||
                    args->rows != q27_gdn_qkvz_m6_workspace::rows ||
                    args->cols != q27_gdn_qkvz_m6_workspace::n_qkv ||
                    args->stride != q27_gdn_qkvz_m6_workspace::k ||
                    args->scratch_bytes < q27_gdn_qkvz_m6_workspace::bytes) {
                return Q27_XE2_BAD_SHAPE;
            }
            if (args->packs == nullptr || args->pack_count != 5) {
                return Q27_XE2_BAD_LAYOUT;
            }
            const q27_xe2_pack_v1 &qkv = args->packs[0];
            const q27_xe2_pack_v1 &z = args->packs[1];
            const q27_xe2_pack_v1 &alpha_beta = args->packs[2];
            const q27_xe2_pack_v1 &dt = args->packs[3];
            const q27_xe2_pack_v1 &a = args->packs[4];
            if (qkv.device_ptr == nullptr ||
                    qkv.bytes != q27_gdn_qkvz_m6_workspace::qkv_pack_bytes ||
                    qkv.layout_id != Q27_XE2_LAYOUT_Q4_0_Q8_1_V1 ||
                    qkv.content_tag != Q27_XE2_QWEN36_27B_Q4_MODEL_TAG ||
                    qkv.role != Q27_XE2_PACK_GDN_QKV ||
                    z.device_ptr == nullptr ||
                    z.bytes != q27_gdn_qkvz_m6_workspace::z_pack_bytes ||
                    z.layout_id != Q27_XE2_LAYOUT_Q4_0_Q8_1_V1 ||
                    z.content_tag != Q27_XE2_QWEN36_27B_Q4_MODEL_TAG ||
                    z.role != Q27_XE2_PACK_GDN_Z ||
                    alpha_beta.device_ptr == nullptr ||
                    alpha_beta.bytes != q27_gdn_qkvz_m6_workspace::alpha_beta_pack_bytes ||
                    alpha_beta.layout_id != Q27_XE2_LAYOUT_F32_GDN_BA_V1 ||
                    alpha_beta.content_tag != Q27_XE2_QWEN36_27B_Q4_MODEL_TAG ||
                    alpha_beta.role != Q27_XE2_PACK_GDN_ALPHA_BETA ||
                    dt.device_ptr == nullptr ||
                    dt.bytes != q27_gdn_qkvz_m6_workspace::gate_vector_bytes ||
                    dt.layout_id != Q27_XE2_LAYOUT_F32_GDN_VECTOR_V1 ||
                    dt.content_tag != Q27_XE2_QWEN36_27B_Q4_MODEL_TAG ||
                    dt.role != Q27_XE2_PACK_GDN_DT ||
                    a.device_ptr == nullptr ||
                    a.bytes != q27_gdn_qkvz_m6_workspace::gate_vector_bytes ||
                    a.layout_id != Q27_XE2_LAYOUT_F32_GDN_VECTOR_V1 ||
                    a.content_tag != Q27_XE2_QWEN36_27B_Q4_MODEL_TAG ||
                    a.role != Q27_XE2_PACK_GDN_A) {
                return Q27_XE2_BAD_LAYOUT;
            }
            q27_gdn_qkvzab_gate_m6_submit(
                *queue, qkv.device_ptr, z.device_ptr,
                static_cast<const float *>(alpha_beta.device_ptr),
                static_cast<const float *>(dt.device_ptr),
                static_cast<const float *>(a.device_ptr),
                static_cast<const float *>(args->input0),
                static_cast<float *>(args->output0),
                static_cast<float *>(args->output1),
                static_cast<float *>(args->output2),
                static_cast<float *>(args->output3), args->scratch);
            return Q27_XE2_OK;
        }
        if (args->op == Q27_XE2_OP_Q5K_GDN_OUT_M6) {
            if (args->input0 == nullptr || args->output0 == nullptr ||
                    args->scratch == nullptr ||
                    args->rows != q27_q5k_gdn_out_m6_workspace::rows ||
                    args->cols != q27_q5k_gdn_out_m6_workspace::n ||
                    args->stride != q27_q5k_gdn_out_m6_workspace::k ||
                    args->scratch_bytes < q27_q5k_gdn_out_m6_workspace::bytes) {
                return Q27_XE2_BAD_SHAPE;
            }
            if (args->packs == nullptr || args->pack_count != 1) {
                return Q27_XE2_BAD_LAYOUT;
            }
            const q27_xe2_pack_v1 &pack = args->packs[0];
            if (pack.device_ptr == nullptr ||
                    pack.bytes != q27_q5k_gdn_out_m6_workspace::pack_bytes ||
                    pack.layout_id != Q27_XE2_LAYOUT_Q5K_GDN_OUT_M6_V1 ||
                    pack.content_tag != Q27_XE2_QWEN36_27B_Q4_MODEL_TAG ||
                    pack.role != Q27_XE2_PACK_GDN_OUTPUT) {
                return Q27_XE2_BAD_LAYOUT;
            }
            q27_q5k_gdn_out_m6_submit(
                *queue, pack.device_ptr, static_cast<const float *>(args->input0),
                static_cast<float *>(args->output0), args->scratch);
            return Q27_XE2_OK;
        }
        return Q27_XE2_DECLINED;
    } catch (...) {
        /* SYCL does not give the C boundary a proof that no work reached the queue. */
        return Q27_XE2_SUBMIT_STATE_UNKNOWN;
    }
}

const q27_xe2_module_v1 module = {
    Q27_XE2_ABI_MAGIC,
    Q27_XE2_ABI_VERSION,
    sizeof(q27_xe2_module_v1),
    "qwen27-xe2-experimental",
    Q27_XE2_BUILD_ID,
    Q27_XE2_TARGET_ARCH,
    Q27_XE2_TOOLCHAIN_ABI,
    (UINT64_C(1) << Q27_XE2_OP_SMOKE_AXPY) |
        (UINT64_C(1) << Q27_XE2_OP_Q6K_M6_TOP1) |
        (UINT64_C(1) << Q27_XE2_OP_GDN_QKVZ_M6) |
        (UINT64_C(1) << Q27_XE2_OP_GDN_QKVZAB_M6) |
        (UINT64_C(1) << Q27_XE2_OP_GDN_QKVZAB_GATE_M6) |
        (UINT64_C(1) << Q27_XE2_OP_Q5K_GDN_OUT_M6),
    query_workspace,
    launch,
};

} // namespace

extern "C" const q27_xe2_module_v1 *q27_xe2_module_get_v1(void) {
    return &module;
}
