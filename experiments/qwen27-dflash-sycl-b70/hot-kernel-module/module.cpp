#include "q27_xe2_module.h"

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
        uint32_t,
        uint32_t,
        q27_xe2_workspace_v1 *workspace) {
    if (workspace == nullptr) {
        return Q27_XE2_BAD_ARGUMENT;
    }
    if (op != Q27_XE2_OP_SMOKE_AXPY) {
        return Q27_XE2_DECLINED;
    }
    workspace->bytes = 0;
    workspace->alignment = 1;
    return Q27_XE2_OK;
}

int32_t launch(const q27_xe2_launch_v1 *args) {
    /* Complete validation before q.submit: all failures below are fallback-safe. */
    if (args == nullptr || args->struct_size < sizeof(q27_xe2_launch_v1)) {
        return Q27_XE2_BAD_ABI;
    }
    if (args->op != Q27_XE2_OP_SMOKE_AXPY) {
        return Q27_XE2_DECLINED;
    }
    if ((args->flags & Q27_XE2_QUEUE_IS_IN_ORDER) == 0 ||
        args->queue == nullptr || args->input0 == nullptr ||
        args->output0 == nullptr || args->cols == 0) {
        return Q27_XE2_BAD_ARGUMENT;
    }

    auto *queue = static_cast<sycl::queue *>(args->queue);
    const auto *input = static_cast<const float *>(args->input0);
    auto *output = static_cast<float *>(args->output0);
    const size_t count = args->cols;
    const float alpha = args->scalar0;

    try {
        queue->submit([&](sycl::handler &handler) {
            handler.parallel_for<smoke_axpy_kernel>(sycl::range<1>(count), [=](sycl::id<1> index) {
                output[index] += alpha * input[index];
            });
        });
    } catch (...) {
        /* SYCL does not give the C boundary a proof that no work reached the queue. */
        return Q27_XE2_SUBMIT_STATE_UNKNOWN;
    }
    return Q27_XE2_OK;
}

const q27_xe2_module_v1 module = {
    Q27_XE2_ABI_MAGIC,
    Q27_XE2_ABI_VERSION,
    sizeof(q27_xe2_module_v1),
    "qwen27-xe2-smoke",
    Q27_XE2_BUILD_ID,
    Q27_XE2_TARGET_ARCH,
    Q27_XE2_TOOLCHAIN_ABI,
    UINT64_C(1) << Q27_XE2_OP_SMOKE_AXPY,
    query_workspace,
    launch,
};

} // namespace

extern "C" const q27_xe2_module_v1 *q27_xe2_module_get_v1(void) {
    return &module;
}
