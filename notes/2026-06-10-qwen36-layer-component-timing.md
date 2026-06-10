# Qwen3.6 Quark INT8 Layer Timing Probe

Date: 2026-06-10

## Context

Target remains `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` on four Intel B70 XPUs with the accepted TP4, 32K, no-prefix-cache, PIECEWISE graph configuration.

This pass tried to answer where the single-request decode time is going without changing model weights, quantization, context length, or accepted serving settings.

## Runs

Artifacts:

- `data/qwen36-quark-int8-tp4-noprefix-layer-timing-p512n128-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-layer-timing-print-p512n128-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-layer-timing-signal-p512n128-20260610.json`
- `patches/vllm-qwen36-layer-component-timing-20260610.patch`

Final diagnostic run:

- Prompt/output: 512 input tokens, 128 output tokens
- Timing env: `VLLM_XPU_DECODE_TIMING=1`, `VLLM_XPU_DECODE_TIMING_SYNC=1`, `VLLM_XPU_DECODE_TIMING_PRINT_EVERY=64`, `VLLM_XPU_DECODE_TIMING_RANK=0`
- Client throughput with synchronized timing enabled: 28.83 corrected output tok/s, 11.06 e2e tok/s, 7169 ms TTFT
- These throughput numbers are diagnostic only. The synchronization instrumentation materially slows/changes the run.

Useful rank-0 timing prints from `/tmp/qwen36-quark-int8-tp4-layer-timing-32k-noprefix-signal-20260610.log`:

- `gpu_model_runner.model_forward`: ~8.55 to 8.59 ms/token
- `gpu_model_runner.compute_logits`: ~0.76 ms/token
- `logits.local_argmax_lm_head`: ~0.53 to 0.54 ms/token
- `gpu_model_runner.sampler`: ~0.15 ms/token
- `gpu_model_runner.select_sample_hidden`: ~0.086 ms/token
- `gpu_model_runner.bookkeeping_sync`: ~0.057 ms/token
- `gpu_model_runner.async_output_tolist`: ~0.04 to 0.06 ms/token
- All-reduce graph-capture prints for small decode-like shapes were usually ~0.08 to 0.13 ms per call, while the 512-token prompt shape printed ~0.21 ms and the 8192-token warmup shape printed ~2.5 ms.

## Lessons

The temporary `qwen3_next` Python layer wrappers did not produce per-layer timings under the graph-replayed decode path. That means Python-side layer probes are not enough for the compiled PIECEWISE graph. The next useful attribution step needs to inspect the compiled graph, XPU queue timings, or selected lower-level kernels rather than wrapping model Python.

The current request-level breakdown points away from scheduler/bookkeeping as the main bottleneck. The dominant area is still the compiled `model_forward` body. Logits/sampling is measurable but secondary, around 0.9 ms/token combined outside model forward for this greedy-style request.

## Decision

No serving change accepted from this pass. The normal backend was restored after the diagnostic run with timing env vars unset.

Next no-quality-loss targets:

- Profile the compiled graph/kernel queue inside `model_forward`.
- Audit logits/argmax path for avoidable work in greedy/single-sequence decode.
- Continue treating all-reduce as secondary unless lower-level traces show graph replay communication costs larger than the Python-visible capture timings.
