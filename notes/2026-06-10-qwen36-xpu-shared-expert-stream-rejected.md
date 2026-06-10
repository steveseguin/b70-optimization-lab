# Qwen3.6 INT8 XPU Shared-Expert Stream Rejected

Date: 2026-06-10

## Context

The accepted Qwen3.6 INT8 runtime remains model-forward-bound during
single-request decode. Each MoE layer includes a shared expert MLP that vLLM can
overlap with router/routed-expert work on CUDA, but the current XPU path keeps
that shared expert serialized because:

- `aux_stream()` only creates auxiliary streams for CUDA-alike platforms.
- `SharedExperts._determine_shared_experts_order()` only allows the
  multi-stream order on `current_platform.is_cuda()`.
- `SharedExperts._run_in_aux_stream()` hard-codes `torch.cuda.stream(...)`.

This candidate tested whether the same math-preserving overlap can be enabled
for Intel XPU with `torch.xpu.Stream()`.

Accepted runtime to preserve:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- TP4, 32K context
- Quark W8A8 INT8, BF16 runtime
- XPU PIECEWISE graph capture
- clone-safe custom-op all-reduce
- prefix caching disabled
- GDN qkvz/ba activation quant reuse: `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`

Recent accepted control:

- `data/qwen36-quark-int8-tp4-noprefix-current-control-continue-20260610.json`
- corrected after-first output: `99.630056 tok/s`
- e2e output: `98.390754 tok/s`
- total client throughput: `196.781509 tok/s`
- client TTFT: `74.773814 ms`

## Candidate

Patch artifact:

- `patches/vllm-qwen36-xpu-shared-experts-stream-candidate-20260610.patch`

Runtime:

- tmux session: `qwen36-tp4-xpu-shared-stream-32k`
- cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-reuseqkvzbaquant-clone-xpushared-envclean-32k-noprefix`
- log:
  `/tmp/qwen36-quark-int8-tp4-xpu-shared-stream-32k-noprefix-20260610.log`
- new flag: `VLLM_XPU_SHARED_EXPERTS_STREAM=1`

The patch:

- added an opt-in `VLLM_XPU_SHARED_EXPERTS_STREAM` env var,
- let `aux_stream()` create `torch.xpu.Stream()` when the flag is enabled,
- allowed `SharedExpertsOrder.MULTI_STREAM_OVERLAPPED` on XPU under that flag,
- switched the shared-expert aux stream context to `torch.xpu.stream(...)` on
  XPU and kept `torch.cuda.stream(...)` on CUDA.

Standalone XPU stream smoke passed when launched with the same library path as
the service:

```text
platform xpu True
aux torch.xpu.Stream(device=xpu:0 ...)
current torch.xpu.Stream(device=xpu:0 ...)
stream smoke ok 1
```

## Result

Startup failed during XPU graph capture before the endpoint became healthy:

```text
RuntimeError: wait method cannot be used for an event associated with a command graph.
```

The stack was inside `torch.xpu.empty_cache()` while entering graph capture from
`vllm/compilation/cuda_graph.py`, after the candidate stream work had run during
warmup/capture.

No speed or quality gate was run because the server never reached `/health`.

## Decision

Reject for the current production candidate.

The idea is still mathematically exact, but the current XPU graph stack is not
safe with this extra stream/event interaction. It may be worth revisiting only
if either:

- XPU graph capture gains safe multi-stream/event handling, or
- vLLM grows an XPU-specific shared-expert overlap that avoids event waits
  inside captured graph regions.

Do not enable XPU shared-expert auxiliary streams with the current 32K PIECEWISE
graph runtime.

## Restore

The candidate source edits were reverted. The accepted runtime was restored:

- tmux session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- endpoint: `http://127.0.0.1:18080`
- `/health`: pass
- restore log:
  `/tmp/qwen36-quark-int8-tp4-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix-restore-20260610.log`

Restore speed sanity:

- artifact:
  `data/qwen36-quark-int8-tp4-noprefix-restore-after-xpushared-reject-r4-20260610.json`
- corrected after-first output: `99.781561 tok/s`
- e2e output: `98.550715 tok/s`
- total client throughput: `197.101430 tok/s`
- client TTFT: `74.107679 ms`

The restored runtime is back in the accepted performance band.
