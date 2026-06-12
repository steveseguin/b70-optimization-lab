# Qwen3.6 First-Decode Route Fixture Plan

This is a CPU-only planning artifact. It converts the compact route fixture into JSONL rows for existing route simulators and kernel microbench scripts.

## Shape

- Hidden size: `2048`
- MoE intermediate size: `512`
- TP-local intermediate size: `128`
- Layers: `40`
- Experts: `256`
- Experts per token: `8`
- MTP layers in config: `1`

## Fixture Summary

- Records emitted: `120`
- Fixtures: `3`
- Layers: `40`
- Global active experts: `215`
- Unique topk tuples: `80`

## Placement Proxy

| policy | mean max rows/group | p95 max rows/group | mean imbalance | p95 imbalance |
|---|---:|---:|---:|---:|
| `contiguous_ep4` | 3.542 | 5.000 | 1.771 | 2.500 |
| `round_robin_ep4` | 3.783 | 5.000 | 1.892 | 2.500 |

Interpretation: one-token/topk-8 decode has only eight routed expert rows per MoE layer. If we switch sparse MoE work to EP, route placement can become imbalanced unless the path replicates hot experts or uses a route-class scheduler. That keeps persistent topk-8 TP-local MoE as the first kernel target.

## TP-Local Memory Estimate

- Expert weights/scales per TP shard: `194.250 MiB`
- Single-token scratch estimate: `0.085968 MiB`

## Generated Artifacts

- JSON summary: `data/qwen36-quark-int8-tp4-firstdecode-route-fixture-plan-20260612ct.json`
- JSONL route rows: `data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl`

## Next Commands

Route placement proxy:

```bash
python3 scripts/qwen36-route-parallelism-sim.py \
  data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl \
  --output-json data/qwen36-quark-int8-tp4-firstdecode-route-parallelism-sim-20260612ct.json \
  --markdown-out data/qwen36-quark-int8-tp4-firstdecode-route-parallelism-sim-20260612ct.md \
  --window-size 1 --stride 1 --max-num-tokens 1
```

Synthetic XPU MoE microbench, only when the serving endpoint is stopped or an isolated XPU is available:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py \
  --route-jsonl data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl \
  --route-layer-regex 'layers[.]9[.]mlp[.]experts' \
  --rows 1 --iterations 100 --warmup 20 \
  --output-json data/qwen36-quark-int8-firstdecode-l9-r1-microbench-20260612ct.json \
  --markdown-out data/qwen36-quark-int8-firstdecode-l9-r1-microbench-20260612ct.md
```
