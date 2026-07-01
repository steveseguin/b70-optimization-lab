# vLLM XPU Step Timing Instrumentation, 2026-06-11

This records the local runtime instrumentation applied in
`/home/steve/src/vllm` for Qwen3.6 W8A8 INT8 decode profiling.

The change is diagnostic only. It is gated by
`VLLM_XPU_DECODE_TIMING=1` and `VLLM_XPU_DECODE_TIMING_STEP_SUMMARY=1`;
production launchers strip these env vars unless
`VLLM_XPU_DECODE_TIMING_ALLOW=1`.

## Files Touched

- `/home/steve/src/vllm/vllm/utils/xpu_decode_timing.py`
- `/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py`
- `/home/steve/llm-optimizations/scripts/summarize-xpu-decode-timing-log.py`
- `/home/steve/llm-optimizations/scripts/launch-qwen36-quark-int8-accepted.sh`

## Runtime Env

```bash
VLLM_XPU_DECODE_TIMING_ALLOW=1
VLLM_XPU_DECODE_TIMING=1
VLLM_XPU_DECODE_TIMING_SYNC=1
VLLM_XPU_DECODE_TIMING_RANK=0
VLLM_XPU_DECODE_TIMING_SUMMARY=1
VLLM_XPU_DECODE_TIMING_PRINT_EVERY=0
VLLM_XPU_DECODE_TIMING_SKIP_FIRST=20
VLLM_XPU_DECODE_TIMING_STEP_SUMMARY=1
VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST=80
VLLM_XPU_DECODE_TIMING_STEP_EVERY=1
```

## Helper Semantics

`xpu_decode_timing.py` now has:

```python
def begin_timing_step(metadata: dict[str, object] | None = None) -> bool:
    ...

def end_timing_step(status: str = "ok") -> None:
    ...
```

When active, `timed_region()` updates both process-global timing totals and
the current step bucket. `end_timing_step()` prints one compact JSON line:

```text
[vllm-xpu-timing-step] {"metadata":{...},"rank":"0","status":"ok","step":144,"summary_by_total_ms":[...]}
```

## Model Runner Hook

`GPUModelRunner.execute_model()` starts a step after batch shape and graph mode
are known, immediately before model execution:

```python
self._xpu_timing_step_active = begin_timing_step(
    {
        "num_reqs": int(num_reqs),
        "num_tokens_unpadded": int(num_tokens_unpadded),
        "num_tokens_padded": int(num_tokens_padded),
        "max_num_scheduled_tokens": int(max_num_scheduled_tokens),
        "cudagraph_mode": str(cudagraph_mode),
        "skip_compiled": bool(skip_compiled),
        "use_spec_decode": bool(use_spec_decode),
        "should_ubatch": bool(should_ubatch),
    }
)
```

`GPUModelRunner.sample_tokens()` closes the step before returning the sync or
async output:

```python
self._finish_xpu_timing_step("ok")
```

There are also early closes for intermediate and pooling returns.

## Artifacts

- `data/qwen36-quark-int8-tp4-step-timing-direct-natural-ignoreeos-p512o128-r1-20260611c.json`
- `data/qwen36-quark-int8-tp4-step-timing-rank0-lines-20260611c.json`
- `data/qwen36-quark-int8-tp4-eager-moe-timing-direct-natural-ignoreeos-p512o64-r1-20260611d.json`
- `data/qwen36-quark-int8-tp4-eager-moe-timing-rank0-lines-20260611d.json`
- `data/qwen36-quark-int8-tp4-post-step-timing-restore-natural-ignoreeos-p512o128-r1-20260611.json`
