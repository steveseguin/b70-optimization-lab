# 2026-07-04 - vLLM XPU kernels detached dirty snapshot

## Context

While continuing Qwen27 optimization, `/home/steve/src/vllm-xpu-kernels` was
found detached at commit `3b4effe` with local tracked edits:

- `csrc/xpu/gdn_attn/spec_decode.hpp`;
- `csrc/xpu/moe_layerlet.cpp`;
- `vllm_xpu_kernels/fused_moe_interface.py`.

This source tree is **not** the active `/home/steve/llm-optimizations` Git
workspace and should not be treated as a clean branch. The diff was preserved
before any new Qwen27 kernel work so the edits are not lost or silently mixed
with future LM-head experiments.

## Patch Snapshot

Patch:

```text
patches/qwen36-35b-quark-int8-b70/vllm-xpu-kernels-detached-dirty-gdn-moe-snapshot-20260704.patch
```

Summary:

- `spec_decode.hpp`: changes `gdn_replayssm_commit_pending_kernel` conv-state
  commit from one work item per `(row, conv_dim, conv_base_pos)` to one work
  item per `(row, conv_dim)`, snapshotting the short conv window locally before
  writing it back. Rationale in the source comments: avoid cross-work-item
  read/write races when `accepted > 0`.
- `moe_layerlet.cpp`: allows `topk_ids` to be either `int64` or `int32` in the
  Qwen36 single-token prologue / full layerlet path by templating the top-k ID
  type and casting to `int64_t` for comparisons.
- `fused_moe_interface.py`: adds `topk_ids_dtype` to a debug/event payload.

## Classification

This is a preserved external-source snapshot, not a promoted Qwen27
optimization and not a LocalMaxxing candidate. It appears related to older
Qwen36 35B GDN ReplaySSM / MoE-layerlet work.

Before using it:

1. restore or branch `/home/steve/src/vllm-xpu-kernels` intentionally;
2. apply the patch in isolation;
3. build the kernels;
4. rerun the relevant Qwen36 canaries and throughput gate;
5. record the result in the Qwen36 35B packet before promotion.

