# 2x B70 Reference

This file records the TP2 / 2x B70 references for the same Qwen3.6 35B Quark
W8A8 INT8 model. These are useful when comparing topology, tensor parallel
size, and memory pressure. They are not the current 4x record lane.

## Best TP2 References

| Run | Shape | Corrected output | Validity |
| --- | --- | ---: | --- |
| [`tp2-latency-truth-p512o256`](../../data/qwen36-quark-int8-tp2-latency-truth-p512o256-metrics-20260612bx.json) | p512/o256, repeat 1 | `91.5923126794016 tok/s` | smoke/reference only |
| [`tp2-latency-truth-p512o256-r3`](../../data/qwen36-quark-int8-tp2-latency-truth-p512o256-r3-metrics-20260612bx.json) | p512/o256, repeat 3 | `91.35105186355895 tok/s` mean | smoke/reference only |
| [`tp2-noprefix-seqs24-single-r4`](../../data/qwen36-quark-int8-tp2-noprefix-seqs24-single-r4-20260611.json) | p512/o512, repeat 4 | `91.24716509862932 tok/s` class | older rejected/reference |
| [`tp2-graph32k-single`](../../data/qwen36-quark-int8-tp2-graph32k-single-20260610.json) | p512/o512, repeat 4 | `86.8477485384133 tok/s` class | older rejected/reference |
| [`tp2-safe-smoke`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-tp2-smoke-summary-20260615tp2safe1.json) | p512/o512, canary smoke | `85.86911405999231 tok/s` | JSON `16/16`, color `16/16`, quality skipped; LocalMaxxing `cmqq4mwgm00yiqo0133bj962q` |

The user's memory that 2x was "closer to 80 tok/s" is directionally right for
the safer TP2 smoke (`85.87 tok/s`), but older raw TP2 measurements reached
about `91 tok/s`. Do not promote the older raw TP2 numbers without rerunning the
current gates.

## Why TP2 Matters

TP2 often showed surprisingly competitive single-session decode because it
reduced communication pressure relative to TP4. That does not make it a better
4-GPU record, but it is useful when diagnosing:

- tensor-parallel allreduce overhead;
- XPU graph capture overhead;
- per-rank memory pressure and KV headroom;
- whether a slowdown is caused by model math or interconnect/runtime behavior.

## Current TP2 Reproduction Smoke

This is the canary-smoke TP2 command preserved in the recovery notes:

Metrics artifact:

- [`tp2-safe-smoke-metrics`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-tp2-smoke-p512o512-20260615tp2safe1.json)
- [`LocalMaxxing submission log`](../../data/localmaxxing-responses/qwen36-35b-quark-int8-b70-valid-2x4x-20260623.submit.log)

```bash
cd /home/steve/llm-optimizations
STAMP=20260615tp2safe1 \
PORT=18125 BASE_URL=http://127.0.0.1:18125 \
CACHE_LABEL=qwen36-ablation-prefill-safe-int8-mixed-workspace-async-tp2-smoke \
TP_SIZE=2 ONEAPI_DEVICE_SELECTOR=level_zero:0,1 ZE_AFFINITY_MASK=0,1 \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
GPU_MEMORY_UTILIZATION=0.90 MAX_NUM_SEQS=24 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=1 JSON_REPEATS=16 COLOR_REPEATS=16 ABLATION_RUN_QUALITY=0 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-mixed-workspace-async-tp2-smoke
```

For a promotable TP2 claim, increase canaries to at least the current TP4 gate
discipline and add the quality suite.
