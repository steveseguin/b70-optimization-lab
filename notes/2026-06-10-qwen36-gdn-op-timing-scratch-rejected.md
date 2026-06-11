# Qwen3.6 GDN Op Timing And Internal Scratch Rejection

Date: 2026-06-10

## Context

Current accepted runtime:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Hardware: 4x Intel Arc Pro B70
- Runtime: vLLM XPU TP4, Quark W8A8 INT8, 32K context, `--no-enable-prefix-caching`, XPU PIECEWISE graph capture, accepted `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`

## Timing Diagnostic

Added temporary timing scopes behind the existing `VLLM_XPU_DECODE_TIMING=1` path:

- `gdn_attention_core_xpu.native`
- `moe_forward.custom_op`
- `moe_forward_shared.custom_op`
- Python MoE sub-stages in `fused_moe_interface.py`

Diagnostic launch used sync timing, so the endpoint throughput is not a valid candidate speed result. The useful signal is the relative op timing.

Key timing summary from `/tmp/qwen36-quark-int8-tp4-op-timing-32k-noprefix-20260611.log`:

- `gpu_model_runner.model_forward`: `112` calls, `1395.438773 ms` total, `12.459275 ms` average
- `gdn_attention_core_xpu.native`: `4288` calls, `403.449564 ms` total, `0.094088 ms` average
- `gpu_model_runner.compute_logits`: `0.776758 ms` average
- `logits.local_argmax_lm_head`: `0.542066 ms` average
- `gpu_model_runner.sampler`: `0.156957 ms` average

The live GDN prints during graph replay were consistently around `0.083-0.105 ms` per call. MoE sub-stage totals were polluted by graph capture and are not reliable steady-state decode timings.

Diagnostic throughput artifact: `data/qwen36-quark-int8-tp4-noprefix-op-timing-p512n128-20260611.json`.

## Rejected Candidate

Candidate: opt-in internal GDN scratch reuse for `q`, `k`, `v`, `b`, `a`, and `conv_states_tmp`, gated behind `VLLM_XPU_GDN_REUSE_INTERNAL_SCRATCH=1`.

Result:

- Build succeeded with oneAPI 2025.3 using `build/xpu-c-only-2025`.
- Startup and graph capture completed.
- First frontdoor exact-OK smoke failed with HTTP 500.
- Worker hit `UR_RESULT_ERROR_DEVICE_LOST`; follow-on shutdown saw `UR_RESULT_ERROR_OUT_OF_RESOURCES`.
- No speed or quality numbers are valid because it failed the first generation request.

Failure log: `/tmp/qwen36-quark-int8-tp4-gdn-internal-scratch-32k-noprefix-20260611.log`.

Decision: reject. Do not enable or rebuild the scratch-reuse path. Reusing internal GDN buffers across captured graph nodes is not safe on this stack.

Recovery:

- Restored package shared objects from `vllm_xpu_kernels/_xpu_C.abi3.so.backup-20260611-gdn-internal-scratch-pretest` and `vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so.backup-20260611-gdn-internal-scratch-pretest`.
- Relaunched accepted full-clone backend.
- `/health` passed.
- Frontdoor exact-OK smoke returned `OK`.

Restore log: `/tmp/qwen36-quark-int8-tp4-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix-restore-after-scratch-reject-20260611.log`.

## Next Useful Direction

GDN is still worth targeting, but not by naive tensor scratch reuse under graph capture. Safer follow-ups:

- Inspect whether decode-only `causal_conv1d` plus `gated_delta_rule` can be fused into a single kernel without changing math.
- Add lower-level kernel timing around causal-conv versus gated-delta in a non-reuse diagnostic.
- Continue dense boundary work where exact semantics are easier to preserve.
