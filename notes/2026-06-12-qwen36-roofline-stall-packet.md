# Qwen3.6 35B INT8 Roofline/Stall Packet

Date: 2026-06-12

Model:
`nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`

Accepted service:

- Backend: `127.0.0.1:18080`
- Public frontdoor: `127.0.0.1:8000`, paused for remote generation with local
  bypass enabled.
- Status snapshot:
  `data/qwen36-quark-int8-tp4-roofline-packet-frontdoor-status-20260612al.json`
- XPU process snapshot:
  `data/qwen36-quark-int8-tp4-roofline-packet-xpusmi-ps-20260612al.txt`

## Tooling Boundary

Hardware-counter tools are not currently available on PATH:

- `unitrace`: absent
- `vtune`: absent
- `ze_tracer`: absent
- `onetrace`: absent

This packet therefore uses:

- vLLM endpoint metrics and histograms,
- prior synchronized model-forward timing,
- route-exact MoE layer replay,
- grouped-GEMM small-M timing,
- and route-conditioned parallelism simulation.

This is enough to choose the next implementation direction. It is not a
substitute for a future oneAPI/Level-Zero hardware-counter trace.

## Fresh Live C1 Endpoint Measurement

Command:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/measure-openai-endpoint-metrics.py \
  --base-url http://127.0.0.1:8000 \
  --model qwen36-35b-a3b-fp8 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --prompt-tokens 512 \
  --output-tokens 512 \
  --prompt-kind preset \
  --prompt-preset natural-chat \
  --endpoint completions \
  --mode stream \
  --repeats 4 \
  --warmup-output-tokens 64 \
  --skip-vram \
  --ignore-eos \
  --out data/qwen36-quark-int8-tp4-live-c1-p512o512-metrics-20260612al.json
```

Result:

- Corrected after-first output speed: `99.618 tok/s`.
- End-to-end output speed: `98.130 tok/s`.
- Client TTFT: `87.996 ms`.
- vLLM TTFT: `76.166 ms`.
- vLLM decode histogram: `10.039 ms/token`.
- vLLM inter-token histogram: `10.059 ms/token`.

Interpretation:

- The live accepted service is still in the same `~100 tok/s` c1 tier.
- Frontdoor/HTTP/SSE overhead is not hiding a `2x` win; previous in-process
  vLLM checks were also around this tier.
- To reach `>200 tok/s`, decode must drop from about `10.04 ms/token` to below
  `5.0 ms/token`.

## Refreshed MoE Fusion Target Budget

Command:

```bash
python3 scripts/qwen36-moe-fusion-target-budget.py \
  --endpoint-metrics-json data/qwen36-quark-int8-tp4-live-c1-p512o512-metrics-20260612al.json \
  --model-forward-summary-json data/qwen36-quark-int8-tp4-sync-modelonly-summary-20260612u.json \
  --route-replay-json \
    data/qwen36-quark-int8-moe-routecapture6-layer9-startscan-r15-20260611.json \
    data/qwen36-quark-int8-moe-routecapture5-layer20-startscan-r15-20260611.json \
    data/qwen36-quark-int8-moe-routecapture6-layer9-active-offset-gemm-20260612ai.json \
  --smallm-timing-json data/qwen36-quark-int8-tp4-grouped-gemm-smallm-timing-20260612an.json \
  --target-tok-s 200 \
  --rows 1 \
  --primary-rows 1 \
  --topk 8 \
  --output-json data/qwen36-quark-int8-moe-fusion-target-budget-20260612al.json \
  --markdown-out data/qwen36-quark-int8-moe-fusion-target-budget-20260612al.md
```

Key numbers:

- Current decode: `10.039 ms/token`.
- Model-forward timing: `8.438 ms/token`.
- Outside-forward estimate: `1.600 ms/token`.
- Required model-forward saving for `200 tok/s`: `5.039 ms/token`.
- Required saving across `40` MoE layers: `125.973 us/layer`.
- Exact current `xpu_fused_moe`: `294.145 us/layer`.
- Exact preallocated staged path: `220.530 us/layer`.
- Required layerlet target: `168.173 us/layer`.
- Two independent grouped-GEMM floor: `193.538 us`.
- One-dispatch floor proxy: `100.506 us`.

Decision:

- A two-dispatch non-speculative MoE path cannot reach `>200 tok/s` by itself.
  Its floor is already above the `168 us/layer` target.
- A viable non-speculative path needs a one-dispatch/resident layerlet or an
  equivalent persistent command path that fuses route/remap, quant1, GEMM1,
  activation, quant2, GEMM2, and gather.
- If a one-layer replay cannot beat roughly `168 us/layer` with exact parity,
  the `>200 tok/s` path should move to target-verified speculation.

## Grouped-GEMM Roofline Estimate

Existing artifact:

- `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-roofline-20260612ak.md`

Key numbers:

- Exact `gemm1`, mean route-window shape `M=128, K=2048, N=256`,
  `43.4` active experts: `97.138 us`, `1.413 effective TOPS`.
- Exact `gemm2`, mean route-window shape `M=128, K=128, N=2048`,
  `43.4` active experts: `92.556 us`, `0.725 effective TOPS`.

Interpretation:

- Effective TOPS are very low for B70-class INT8 hardware.
- The low value is consistent with small-M/skewed-expert grouped-GEMM
  underutilization, launch/control overhead, non-ideal W8A8 kernel routing, or
  a combination of those.
- This supports tile-native/persistent MoE work over more service flags.

## Prompt-Class Route Parallelism Simulation

Command:

```bash
python3 scripts/qwen36-route-parallelism-sim.py \
  data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-*.jsonl \
  data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --layer-regex 'mlp[.]experts' \
  --stage-regex '^quark_int8_apply$' \
  --min-num-tokens 1 \
  --max-num-tokens 1 \
  --window-size 16 \
  --stride 16 \
  --max-windows-per-layer 40 \
  --baseline-tp 4 \
  --gpu-count 4 \
  --hotset-sizes 16,32,64 \
  --output-json data/qwen36-quark-int8-tp4-promptclass-plus-route6-parallelism-sim-20260612al.json \
  --markdown-out data/qwen36-quark-int8-tp4-promptclass-plus-route6-parallelism-sim-20260612al.md
```

Inputs:

- `5485` matched route records.
- `325` route windows across prompt-class captures plus routecapture6.

Policy summary:

| policy | mean pressure | p95 pressure | mean comm rows | max memory rel |
|---|---:|---:|---:|---:|
| `ep4_contiguous` | 1.279 | 1.469 | 1.000 | 1.000 |
| `ep4_greedy_static` | 1.213 | 1.406 | 1.000 | 1.000 |
| `ep4_hot16_replicated_greedy` | 1.022 | 1.062 | 0.549 | 1.188 |
| `ep4_hot32_replicated_greedy` | 1.001 | 1.000 | 0.356 | 1.375 |
| `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.155 | 1.750 |
| `tp2_ep2_greedy_static` | 1.079 | 1.172 | 1.000 | 1.000 |

Interpretation:

- Plain EP policies carry load-imbalance risk and still move all routed rows.
- Hot-expert replication looks robust across prompt classes as a routing proxy.
- `hot64` replication nearly eliminates load imbalance and reduces the
  communication-row proxy to `0.155`, at `1.75x` expert-memory cost.
- This is a serious medium-term path if TP communication or remote-expert
  movement proves significant, but it does not replace the one-layer persistent
  layerlet as the immediate non-speculative kernel target.

## Current Decision

The next implementation branch should be:

1. **One-layer persistent MoE layerlet replay for layer 9.**
   Start with fixed routecapture6 metadata and exact parity against
   `xpu_fused_moe`. The pass/fail budget is `<=168 us/layer`; a stretch target
   is `<=150 us/layer` to leave room for non-MoE overhead.

2. **Keep target-verified speculation as the parallel high-upside path.**
   If the one-layer layerlet cannot beat the budget, non-speculative kernel
   work is unlikely to reach `>200 tok/s` quickly. The verifier-owned escrow
   design then becomes the primary path.

3. **Do not spend more time on small offset/active-offset ABI variants.**
   The latest exact active-offset gate did not beat plain offset GEMM, and both
   remain above the target budget.

4. **Use hot-expert replication only after a communication/stall trace or
   layerlet result justifies it.**
   The routing proxy is promising enough to keep, but it is a larger runtime
   layout change and should not preempt the layerlet proof.

Quality gates for any candidate:

- Exact route-replay parity: `max_abs_diff=0.0` against current
  `xpu_fused_moe`.
- Accepted-service provenance sentinels after restore.
- Short prompt-class quality suite.
- Long-context needle.
- Device-lost scan and 30-60 minute c1 soak before production promotion.
