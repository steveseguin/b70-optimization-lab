# TASK: Implement the ReplaySSM spec-verify as a fused _xpu_C/SYCL kernel

Work in `/home/steve/src/vllm` + `/home/steve/src/vllm-xpu-kernels`.

## Status (your prior work, committed)
Commit `ff4cf370f` ported the ReplaySSM GDN spec-verify algorithm into the fork
behind `VLLM_XPU_GDN_REPLAYSSM_SPEC=1`, reimplemented in vectorized torch ops
(Triton fails on XPU). It is **algorithmically correct** — the torch algebra
matches the reference, and the endpoint accepts drafts at 100% (Mean acceptance
length 2.00). The parity bug is functionally fixed.

**Blocker:** the vectorized torch/einsum/scatter ops per GDN layer run at
0.1-0.3 tok/s. Needs a **fused SYCL kernel**.

## Task
Implement the **same algorithm** (do NOT change the math — it's validated) as a
single fused `_xpu_C` SYCL kernel in `/home/steve/src/vllm-xpu-kernels`, modeled
on the existing `gdn_attention` / `gdn_attention_core_xpu` op there. Replace the
slow torch-op reconstruction in `gdn_replayssm_spec_decode` (vllm side,
`vllm/model_executor/layers/mamba/gdn_linear_attn.py` + `_xpu_ops.py`) with a
call to this kernel.

The kernel must do, in one launch per GDN layer per verify step:
- the output-only reconstruction `o = alpha * (S0 @ q) + sum_j w_j * (k_j·q) * d_j`
  over the per-request spec sequences (ring of last L `(d,k,g)` + frozen `S0`);
- the chunked delta-rule `(I+A)^{-1}` UT-transform for the draft window;
- ring append + cursor advance + the `ring_len >= 2*max_spec_len` early-flush.
Conv state: thread as a sequence (no slot-copy).

Reference algorithm source (read it; reimplement its math in SYCL, not Triton):
- `/home/steve/src/ReplaySSM/vllm/model_executor/layers/fla/ops/gdn_replayssm_spec_decode.py`
- `/home/steve/src/ReplaySSM/vllm/model_executor/layers/mamba/ops/selective_state_update_replayssm_spec.py`

Build: `/home/steve/llm-optimizations/scripts/build-vllm-xpu-kernels-xpu-c-only.sh`
then copy `_xpu_C.abi3.so` + `libgrouped_gemm_xe_2.so` into `vllm_xpu_kernels/`.

## MUST validate with the endpoint canary (the gate)
```
cd /home/steve/llm-optimizations
MODEL_PATH=/mnt/fast-ai/qwen36-quark-int8-fp8-mtp-hybrid \
SERVER_LAUNCHER=scripts/launch-qwen36-quark-int8-accepted.sh \
VLLM_QWEN35_MTP_FORCE_FP8_BLOCK=1 VLLM_XPU_GDN_REPLAYSSM_SPEC=1 \
VLLM_EXTRA_ARGS='--speculative-config {"method":"mtp","num_speculative_tokens":1}' \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":128}' \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 \
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
GPU_MEMORY_UTILIZATION=0.95 ABLATION_FAST_GRAPH_AUTOCONFIG=0 READINESS_TIMEOUT_S=2400 \
bash scripts/run-qwen36-ablation-candidate.sh tp4-mtp-k1-replayssm-fused
```
Success = json-canary **96/96** AND color-canary **96/96** AND corrected tok/s
within ~30% of the 93.55 baseline (NOT 0.1-0.3 tok/s). Report real acceptance +
tok/s + canary counts.

## Hard rules
- Implement the VALIDATED algorithm — do not change the ReplaySSM math.
- One fused SYCL kernel, not scattered torch ops. No Triton.
- Don't change no-spec decode/prefill.
- COMMIT when the endpoint canary passes; update notes/codex-gdn-parity-fix.md.
- If the fused kernel can't be made to pass canary at speed, STOP and write the
  precise blocker (which op, what speed you got, what the profile says).
