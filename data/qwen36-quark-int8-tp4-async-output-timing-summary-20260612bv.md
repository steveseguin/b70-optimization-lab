# Qwen3.6 Quark INT8 TP4 Async Output Timing

Date: 2026-06-12

Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`

Runtime: vLLM/XPU TP4, accepted 32K context launch shape, c1 streaming completions.

Source patch: `patches/vllm-qwen36-async-output-timing-20260612bv.diff`

Note: the patch is the current local `gpu_model_runner.py` lab diff used for
this diagnostic. It includes accumulated runner instrumentation, not only the
small async-output timing hunk.

## Runs

| Run | Flags | Corrected tok/s | vLLM decode ms/token | TPOT ms | Output path |
| --- | --- | ---: | ---: | ---: | --- |
| `20260612bv` | async-output timing only | 88.990 | 11.196 | 11.240 | default nonblocking copy, `.tolist()` |
| `20260612bw` | timing + reuse buffer + fast scalar list | 88.595 | 11.246 | 11.290 | reusable pinned CPU buffer, scalar fast path |

The runs are intentionally slower than the accepted baseline because extra timing/logging was enabled.

## Key Measurements

| Measurement | Default path | Reuse/fast path |
| --- | ---: | ---: |
| `AsyncGPUModelRunnerOutput.get_output()` total mean | 3.815 ms | 3.873 ms |
| Event synchronize mean | 3.798 ms | 3.840 ms |
| Copy-submit mean | 0.095 ms | 0.094 ms |
| Token-list/scalar conversion mean | 0.010 ms | 0.026 ms |
| RPC max output enqueue mean | 4.494 ms | 4.432 ms |
| RPC max worker function mean | 0.348 ms | 0.346 ms |

## Interpretation

- The response-materialization cost is almost entirely `async_copy_ready_event.synchronize()`.
- The copied token tensor is tiny: rank 0, c1, no logprobs, source dtype `torch.int32`, source shape `[1,1]`.
- Reusing the pinned CPU output buffer fires correctly but does not reduce the synchronization wait.
- Fast scalar extraction is not useful here; `.tolist()` is not the bottleneck.
- The old "output path" hypothesis should be reframed: this host wait is where queued XPU model/sampler/copy work becomes visible, not a Python object-conversion problem.

## Follow-Up Gates

1. Restore accepted backend and rerun provenance plus no-thinking quality before promoting any code path. Rerun passed on the same restored backend after one transient failed artifact.
2. Attribute the event wait with device-side profiling: model forward, sampler, D2H token copy, and collectives.
3. Test TP2 and direct c1 runner only after the accepted TP4 backend is clean again.
4. Treat output-buffer/list changes as exhausted unless a future device timeline proves a different host copy shape.

## Acceptance Rerun

- Process env check found no leaked async-output/reuse/fast-output timing flags in the APIServer, EngineCore, or TP0 worker.
- Provenance rerun passed both tracked prefixes and sentinel token IDs: `4752`, `11436`, `198`.
- No-thinking quality rerun passed all exact cases, repeat stability, and baseline matching.
