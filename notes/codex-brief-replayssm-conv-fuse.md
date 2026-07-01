# TASK: Fuse the GDN spec-verify CONV/spec staging into one native kernel

Work in `/home/steve/src/vllm` + `/home/steve/src/vllm-xpu-kernels`. Resume your
own ReplaySSM port (commits ff4cf370f, 74feabf9d, 62d0e50).

## Status (your work)
The ReplaySSM recurrent verify is now a fused `_xpu_C` kernel at ~0.020 ms/call
(fast + correct). The **only remaining slow path** is the conv/spec staging per
GDN layer per verify step — still scattered torch ops: conv slot-copy,
`causal_conv1d_update`, gather/pad, `torch.where`, pending conv `index_copy`.
Endpoint is 0.1-0.4 tok/s because of THESE ops, not the recurrent kernel.

## Task
Replace that scattered conv/spec staging with ONE fused native kernel (SYCL,
`_xpu_C`) that, per GDN layer per verify step, threads the causal-conv state as
a **sequence** across the per-request spec positions (no slot-copy, no per-row
torch ops), and stages the spec rows for the (already-fast) recurrent kernel.
Model it on the existing fused conv/causal_conv1d ops already in vllm-xpu-kernels.

The math must be unchanged (the recurrent kernel + this conv staging together
must reproduce the validated ReplaySSM output). No new abstractions — fuse the
existing per-layer torch-op sequence into a kernel.

Build: `/home/steve/llm-optimizations/scripts/build-vllm-xpu-kernels-xpu-c-only.sh`
then copy `_xpu_C.abi3.so` + `libgrouped_gemm_xe_2.so` into `vllm_xpu_kernels/`.

## MUST validate with the endpoint canary (the gate — speed now matters)
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
bash scripts/run-qwen36-ablation-candidate.sh tp4-mtp-k1-replayssm-convfused
```
Success = json-canary **96/96** AND color-canary **96/96** AND corrected tok/s
within ~30% of the 93.55 baseline. Report real acceptance + tok/s + canary counts.

## Hard rules
- Fuse the EXISTING conv/spec-staging ops into one kernel. Don't change the
  validated math. No slot-copy.
- No Triton. Don't touch no-spec decode/prefill.
- COMMIT when canary passes; update notes/codex-gdn-parity-fix.md.
- If it still can't hit the speed gate, STOP and profile: report which op dominates
  the step (kernel timings), so the next step is targeted, not a guess.
