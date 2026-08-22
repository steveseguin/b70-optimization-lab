# Qwen3.8 mtp.fc INT4 integration patch (default-off)

Date: 2026-08-22. Applies to the pinned vLLM checkout at `/home/steve/src/vllm`.
Prereg: [integration prereg](../../experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-mtp-fc-int4-integration-prereg.md).

## What it does

Routes the Qwen3.x MTP `fc` (bias-free `ColumnParallelLinear(10240, 5120,
gather_output=True)`) through the operator-qualified eager W4A16 kernel,
behind a default-off door. Off is byte-identical to stock (FP16 path).

- `vllm/envs.py`: registers `VLLM_XPU_MTP_FC_INT4` (default 0). Because
  `compile_factors()` starts from all env vars minus an ignore set, the
  door auto-forks the torch.compile cache key - no separate wiring.
- `vllm/model_executor/models/qwen3_next_mtp.py`: when the door is on,
  loads the frozen packed buffers (fail-closed on sha; never a silent FP16
  fallback), and replaces only the local matmul with
  `int4_gemm_w4a16(x, packed_storage.t(), None, scales, qzero, 128, None,
  True)` - the exact call and 8th-arg `input_dependency=True` the operator
  screen validated - then reuses the identical `tensor_model_parallel_all_gather`.
  The collective and its ordering are untouched.

## Dependencies (pinned)

- Packed buffers materialized + verified by
  `experiments/qwen38-27b-b70/scripts/materialize_mtp_fc_int4_buffers_20260822.py`
  at `/home/steve/qwen38-mtp-fc-int4-packed-buffers-20260822` (rank0/rank1
  `packed.pt`, file shas hardcoded in the patch, tensor shas match the four
  frozen operator-prereg identities).
- Runtime env `VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER=1` must be set (the
  operator-screen completion-publication contract).
- Patch file: `vllm-mtp-fc-int4-default-off-20260822.diff`, SHA-256
  `95fca14c87dabbec6de40f2089985880fa2a604a47d4796123a3254eb5a0a49c`.

## Trust boundary

This patch is NOT trusted until it passes the prereg's six-gate ladder on a
FRESH sealed compile-cache (new namespace, not b991/f358), starting with the
eager-parity gate. Default-off + fail-closed load are the safety nets; the
gates are the proof. No promoted result uses this until the ladder is green.
