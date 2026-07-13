#ifndef Q27_XE2_MODULE_H
#define Q27_XE2_MODULE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define Q27_XE2_ABI_MAGIC UINT64_C(0x5132375845324d31)
#define Q27_XE2_ABI_VERSION 1u
#define Q27_XE2_GETTER_SYMBOL "q27_xe2_module_get_v1"

#define Q27_XE2_LAYOUT_Q6K_M6_TOP1_V1 UINT64_C(0x51364d3600000001)
#define Q27_XE2_LAYOUT_Q4_0_Q8_1_V1 UINT64_C(0x5134513800000001)
#define Q27_XE2_QWEN36_27B_Q4_MODEL_TAG UINT64_C(0x20c9c45d4d25b492)

enum q27_xe2_status {
    Q27_XE2_OK = 0,

    /* These statuses guarantee that no device work was submitted. */
    Q27_XE2_DECLINED = 1,
    Q27_XE2_BAD_ABI = 2,
    Q27_XE2_BAD_ARGUMENT = 3,
    Q27_XE2_BAD_LAYOUT = 4,
    Q27_XE2_BAD_SHAPE = 5,

    /* Queue state may be unknown. The caller must not run a fallback. */
    Q27_XE2_SUBMIT_STATE_UNKNOWN = 100
};

enum q27_xe2_op {
    Q27_XE2_OP_SMOKE_AXPY = 1,
    Q27_XE2_OP_Q6K_M6_TOP1 = 2,
    Q27_XE2_OP_GDN_FUSED = 3
};

enum q27_xe2_launch_flags {
    Q27_XE2_QUEUE_IS_IN_ORDER = 1u << 0
};

enum q27_xe2_pack_role {
    Q27_XE2_PACK_TARGET_LM_HEAD = 1,
    Q27_XE2_PACK_DRAFT_LM_HEAD = 2,
    Q27_XE2_PACK_GDN_QKV = 3,
    Q27_XE2_PACK_GDN_ALPHA_BETA = 4,
    Q27_XE2_PACK_GDN_OUTPUT = 5
};

struct q27_xe2_pack_v1 {
    const void *device_ptr;
    uint64_t bytes;
    uint64_t layout_id;
    uint64_t content_tag;
    uint32_t role;
    uint32_t reserved0;
};

struct q27_xe2_launch_v1 {
    uint32_t struct_size;
    uint32_t op;
    uint32_t flags;
    uint32_t reserved0;

    /* Borrowed sycl::queue*. Valid only for the negotiated toolchain ABI. */
    void *queue;

    const void *input0;
    const void *input1;
    void *output0;
    void *state0;
    void *scratch;
    uint64_t scratch_bytes;

    const struct q27_xe2_pack_v1 *packs;
    uint32_t pack_count;
    uint32_t rows;
    uint32_t cols;
    uint32_t stride;

    float scalar0;
    float scalar1;
    uint64_t user_tag;
};

struct q27_xe2_workspace_v1 {
    uint64_t bytes;
    uint64_t alignment;
};

typedef int32_t (*q27_xe2_query_workspace_fn)(
    uint32_t op,
    uint32_t rows,
    uint32_t cols,
    struct q27_xe2_workspace_v1 *workspace);

typedef int32_t (*q27_xe2_launch_fn)(const struct q27_xe2_launch_v1 *launch);

struct q27_xe2_module_v1 {
    uint64_t abi_magic;
    uint32_t abi_version;
    uint32_t struct_size;
    const char *module_name;
    const char *module_build_id;
    const char *target_arch;

    /* Must exactly match the host before queue is interpreted as sycl::queue*. */
    const char *toolchain_abi;
    uint64_t supported_ops;

    q27_xe2_query_workspace_fn query_workspace;
    q27_xe2_launch_fn launch;
};

typedef const struct q27_xe2_module_v1 *(*q27_xe2_get_module_v1_fn)(void);

const struct q27_xe2_module_v1 *q27_xe2_module_get_v1(void);

#ifdef __cplusplus
}
#endif

#endif
