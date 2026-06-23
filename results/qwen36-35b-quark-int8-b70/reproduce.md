# Reproduce Qwen3.6 35B B70 Results

These commands are starting points. Always check
[`validity-gates.md`](validity-gates.md) before treating a run as promotable.

## 4x Strict-Valid Current Baseline

This reproduces the current strict-valid TP4 lane identity at the same level as
the `93.55 tok/s` deep gate. Use a new stamp and label when rerunning.

```bash
cd /home/steve/llm-optimizations
STAMP=$(date +%Y%m%d%H%M%S) \
VLLM_XPU_GDN_REPLAYSSM_SPEC=0 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}' \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 \
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
GPU_MEMORY_UTILIZATION=0.90 \
VLLM_EXTRA_ARGS='--uvicorn-log-level warning' \
METRICS_REPEATS=1 JSON_REPEATS=128 COLOR_REPEATS=256 ABLATION_RUN_QUALITY=1 \
bash scripts/run-qwen36-ablation-candidate.sh \
  prefill-safe-int8-mixed-workspace-async-deep-gate-rerun
```

Expected class:

- corrected output throughput around `93.55 tok/s`;
- JSON `128/128`;
- color `256/256`;
- quality suite pass.

Reference artifacts:

- [`deep-gate-summary`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-summary-20260615a13deep2.json)
- [`deep-gate-metrics`](../../data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-p512o512-20260615a13deep2.json)

## 4x Legacy LocalMaxxing-Approved Shape

The approved record was produced with the server identity captured in
[`localmaxxing-qwen36-35b-quark-int8-exacthf-20260612ak.json`](../../data/localmaxxing-qwen36-35b-quark-int8-exacthf-20260612ak.json).
The key server flags were:

```bash
VLLM_USE_V1=1 VLLM_TARGET_DEVICE=xpu \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=1 \
VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1 \
VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT=1 \
VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1 \
VLLM_XPU_QUARK_W8A8_MOE=1 \
VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone \
ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 \
CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 \
FI_TCP_IFACE=eth1 CCL_KVS_IFACE=eth1 \
vllm serve /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --host 127.0.0.1 --port 18080 \
  --trust-remote-code \
  --served-model-name qwen36-35b-a3b-fp8 \
  --dtype auto --quantization quark \
  --tensor-parallel-size 4 --pipeline-parallel-size 1 \
  --distributed-executor-backend mp \
  --max-model-len 32768 \
  --max-num-batched-tokens 8192 \
  --max-num-seqs 48 \
  --gpu-memory-utilization 0.95 \
  --kv-cache-dtype auto \
  --no-enable-prefix-caching \
  --language-model-only \
  --compilation-config '{"cudagraph_mode":"PIECEWISE"}' \
  --generation-config vllm
```

If rerunning this for a new claim, add current JSON/color/quality gates. Do not
submit based only on the older approval.

## 2x Smoke Reference

See [`2x-b70-reference.md`](2x-b70-reference.md) for the exact TP2 command. The
safe TP2 smoke should land near `85.87 tok/s`; older raw TP2 references reached
about `91 tok/s`.

## Validation Harness Notes

The main orchestrator for this lane is:

```bash
bash scripts/run-qwen36-ablation-candidate.sh <label>
```

It writes:

- `data/qwen36-ablation-<label>-summary-<stamp>.json`;
- `data/qwen36-ablation-<label>-p512o512-<stamp>.json`;
- `data/qwen36-ablation-<label>-json-repeatN-<stamp>.json`;
- `data/qwen36-ablation-<label>-color-repeatN-<stamp>.json`;
- server and XPU health logs.

For any promoted result, copy the exact label/stamp paths into the result note
or ledger instead of relying on terminal history.
