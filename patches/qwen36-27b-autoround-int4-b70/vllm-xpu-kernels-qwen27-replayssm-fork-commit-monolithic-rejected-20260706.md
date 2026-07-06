# Rejected patch: monolithic ReplaySSM fork+commit native op

Date: 2026-07-06

Status: rejected before endpoint use; not a benchmark result.

## Attempt

I briefly patched `/home/steve/src/vllm-xpu-kernels` with a new native op:

```text
torch.ops._xpu_C.gdn_replayssm_fork_commit_slots(...)
```

Intended semantics:

1. copy GDN conv state from source slot to destination branch slot;
2. copy ReplaySSM `d_cache`, `k_cache`, `g_cache`, `conv_pending`, and ring metadata;
3. apply accepted-prefix commit to the destination slot if the source had pending state;
4. leave source slots unchanged and ignore invalid/null/out-of-range source or destination rows.

Touched files during the transient attempt:

- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/gdn_attn/spec_decode.hpp`
- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/gdn_attn/gdn_attn_interface.cpp`
- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/ops.h`
- `/home/steve/src/vllm-xpu-kernels/csrc/xpu/torch_bindings.cpp`

## Result

The targeted oneAPI 2025.3 build reached `_xpu_C` link/device compilation, then `ocloc` stayed active for more than 14 minutes without producing a module. I interrupted the build and removed the op from the active source tree.

This failure is not a runtime correctness failure; it is an iteration/build-cost failure. The monolithic all-cache/all-conv fork+commit shape is too large for productive SYCL iteration in this tree.

## Replacement

Use the validated smaller composition instead:

1. copy normal GDN conv state for valid branch rows;
2. call native `gdn_replayssm_copy_slots`;
3. compact to valid `(src, dst)` branch rows;
4. call native `gdn_replayssm_commit_pending`.

Guard:

- `/home/steve/llm-optimizations/scripts/check-gdn-replayssm-fork-commit-slots.py`

Note:

- `/home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-replayssm-branch-fork-composition-guard.md`

If a fused op is needed later, split it into smaller primitives rather than reviving the monolithic op:

- metadata + commit only;
- conv-window accepted-prefix commit only;
- existing native `copy_slots` for ring copy.
