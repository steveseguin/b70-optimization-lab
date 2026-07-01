# TASK: Port the ReplaySSM GDN spec-verify algorithm to XPU (fix the parity bug)

Work in `/home/steve/src/vllm` + `/home/steve/src/vllm-xpu-kernels`. This is the
**proven** fix for the GDN speculative-decode parity bug. **Port the algorithm;
do not reinvent a new abstraction.** Two prior attempts (codex v1 per-position
Python loop; codex v2 native spec-table) both failed by inventing their own
state machinery. Use the reference algorithm below.

## The reference algorithm (read these first)
- `/home/steve/src/ReplaySSM/vllm/model_executor/layers/fla/ops/gdn_replayssm_spec_decode.py` (658 lines)
- `/home/steve/src/ReplaySSM/vllm/model_executor/layers/mamba/ops/selective_state_update_replayssm_spec.py` (776 lines)
- Background/design: `/home/steve/llm-optimizations/notes/2026-06-20-research-plan-replayssm-and-speed.md` and the SGLang RFC sgl-project/sglang#28511.

The math (ReplaySSM, Dao AI Lab 2026): keep a frozen checkpoint `S0` of the GDN
recurrent state `[HV, V, K]`, plus a small per-slot **ring** of the last L steps'
`(d, k, g)` records. On a non-flush step, **append** `(d, k, g)` and reconstruct
the readout **output-only**:
  `o = alpha * (S0 @ q) + sum_j w_j * (k_j·q) * d_j`
where `alpha` = total decay, `w_j` = replay decay of entry j. The full `[V,K]`
state is **never materialized** on a non-flush step; it's folded back into `S0`
only every L committed tokens. Rejected-draft rollback = ring pointer move.

For spec verify, the reference computes the whole draft window's verify output
via the chunked delta-rule `(I+A)^{-1}` UT-transform (output-only) over a ring
carried across verify steps.

## The XPU constraint (critical — this is why a copy won't run)
The reference is **Triton** (`from vllm.triton_utils import tl, triton`). Triton
FLA kernels **fail on this XPU** (`PassManager::run` errors) — that is the entire
reason this fork uses custom `_xpu_C` SYCL ops + Python. So:
- **Do NOT copy the Triton kernels.** Reimplement the reconstruction math in
  **vectorized torch ops** (torch.matmul / bmm / einsum on xpu), which work on
  XPU. The reconstruction is small GEMMs + scalars — straightforward in torch.
- It is OK to be slightly slower than the tensor-core Triton kernel at first;
  **correctness first** (canary 96/96), then optimize. But it must be
  **vectorized**, NOT a Python per-spec-position loop (that was codex v1, 15x too slow).

## What to implement
1. A `gdn_replayssm_spec_decode` Python function (XPU, torch ops) that replaces
   the current spec-verify recurrent path in
   `vllm/model_executor/layers/mamba/gdn_linear_attn.py` (the slot-copy /
   `_xpu_gdn_promote_running_state` / codex v1-v2 paths). It must:
   - run the verify forward output-only over the per-request spec sequences
     (use `spec_query_start_loc`), reconstructing outputs without materializing
     per-draft full states;
   - handle partial acceptance (running state after verify = state at the last
     accepted position) — this is the edge that broke codex v2;
   - conv state: thread as a sequence too, not a slot-copy.
2. Ring buffers `(d,k,g)` + cursor in the KV/state pool (allocate lazily, reset
   on prefill/COW), gated behind `VLLM_XPU_GDN_REPLAYSSM_SPEC=1` (default off).
3. Honor the reference's **early-flush invariant** exactly:
   `ring_len >= 2 * max_spec_len` (overflow → uninitialized logit fed to the
   rejection sampler → silent state desync).

## MUST validate with the endpoint canary (synthetic tests lied before)
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
bash scripts/run-qwen36-ablation-candidate.sh tp4-mtp-k1-replayssm-port
```
Success = json-canary **96/96** AND color-canary **96/96** (token-identical to
no-spec) AND corrected tok/s within ~30% of the 93.55 baseline (not 6 tok/s).
Report the real acceptance + tok/s + canary counts.

## Hard rules
- PORT the reference algorithm. No new slot-copy / accepted-count / per-position
  abstractions (all proven to fail).
- Vectorized torch ops on XPU; no Triton.
- Don't change no-spec decode or prefill.
- COMMIT when the endpoint canary passes; update
  `/home/steve/llm-optimizations/notes/codex-gdn-parity-fix.md` with real numbers.
- If the port can't pass canary after focused effort, STOP and write the precise
  blocker (which op / which state diverges first), don't spin.
