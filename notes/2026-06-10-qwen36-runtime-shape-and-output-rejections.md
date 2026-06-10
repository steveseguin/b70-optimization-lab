# Qwen3.6 Runtime Shape And Output Rejections

Date: 2026-06-10

## Context

After restoring the accepted TP4 32K no-prefix runtime, I screened runtime-only
changes that should not affect model math or quality:

- `cudagraph_capture_sizes=[1]`
- fast async-output list and reusable copy buffers
- `max_num_seqs=8` with `max_num_batched_tokens=8192`

All tests kept the same model, Quark W8A8 INT8 weights, BF16 runtime, TP4, 32K
context, no prefix caching, PIECEWISE XPU graphs, and clone-safe custom-op
collectives.

## Control

Accepted current control, p512/n512, 8 repeats, direct backend:

- Corrected output tok/s after first chunk: `98.7741`
- Output tok/s end-to-end: `97.5295`
- Mean client TTFT: `76.28 ms`
- Artifact: `data/qwen36-quark-int8-tp4-noprefix-accepted-control-current-20260610.json`

Runtime after restore:

- Session: `qwen36-tp4-noprefix-32k`
- Backend: `http://127.0.0.1:18080`
- Frontdoor: `http://127.0.0.1:8000`
- Restore log: `/tmp/qwen36-quark-int8-tp4-accepted-32k-noprefix-restored7.log`
- Available KV cache memory: `20.67 GiB`
- Reported max concurrency at 32K: `62.65x`
- Backend `/health`: pass
- Frontdoor chat smoke: pass, returned `OK`

## Rejected: Capture Size 1

Runtime delta:

- Compilation config: `{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1]}`
- Log: `/tmp/qwen36-quark-int8-tp4-cg1-32k-noprefix-20260610.log`
- Graph capture time: about `2 s`
- Graph capture memory: `0.46 GiB`

Result:

- Corrected output tok/s after first chunk: `98.0309`
- Output tok/s end-to-end: `96.8097`
- Mean client TTFT: `76.08 ms`
- Artifact: `data/qwen36-quark-int8-tp4-noprefix-cg1-single-20260610.json`

Decision: reject. It reduced graph-capture work but was slower than the
accepted control on the p512/n512 single-request benchmark.

## Rejected: Fast Async Output Flags

Runtime delta:

- `VLLM_XPU_FAST_ASYNC_OUTPUT_LIST=1`
- `VLLM_XPU_REUSE_ASYNC_OUTPUT_COPY_BUFFER=1`
- `VLLM_XPU_ASYNC_OUTPUT_COPY_BUFFER_SLOTS=3`
- Log: `/tmp/qwen36-quark-int8-tp4-fastout-32k-noprefix-20260610.log`

Result:

- Corrected output tok/s after first chunk: `97.6234`
- Output tok/s end-to-end: `96.3972`
- Mean client TTFT: `76.96 ms`
- Artifact: `data/qwen36-quark-int8-tp4-noprefix-fastout-single-20260610.json`

Decision: reject. Host output-copy/list reuse did not improve the current
single-request path.

## Rejected: `max_num_seqs=8`

Runtime delta:

- `max_num_seqs=8`
- `max_num_batched_tokens=8192`
- Capture sizes reduced from
  `[1, 2, 4, 8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96]` to
  `[1, 2, 4, 8, 16]`
- Log: `/tmp/qwen36-quark-int8-tp4-seq8-mbt8192-32k-noprefix-20260610.log`
- Failure artifact:
  `data/qwen36-quark-int8-tp4-noprefix-seq8-mbt8192-device-lost-20260610.json`

The runtime started and served `/health`, but the first p512/n512 benchmark hit:

```text
Exception in thread WorkerAsyncOutputCopy
self.async_copy_ready_event.synchronize()
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
```

After that, the engine repeatedly logged:

```text
No available shared memory broadcast block found in 60 seconds
```

Decision: reject for reliability. Reducing graph shapes is not useful if the
first real generation can lose the device and hang the engine.

## Current Decision

Keep the accepted runtime:

- TP4
- 32K context
- Quark W8A8 INT8
- BF16 runtime
- no prefix caching
- PIECEWISE XPU graph
- max batched tokens `8192`
- max sequences `48`

Do not promote any of the screened runtime-shape/output candidates. The next
performance work needs better decode-path diagnostics or source-level kernel
work, not more blind launch-flag changes.
