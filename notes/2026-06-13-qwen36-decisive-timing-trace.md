# Qwen3.6 Decisive Timing Trace

Date: 2026-06-13

## Result

Completed the first all-rank c1 decode timing pass for the current
`nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` TP4 endpoint.

Artifacts:

- Graph/accepted path request metrics:
  `data/qwen36-quark-int8-tp4-layerfamily-timing-p512o128-20260613r.json`
- Graph/accepted path timing log:
  `data/qwen36-quark-int8-tp4-layerfamily-timing-20260613r.log`
- Graph/accepted path timing summary:
  `data/qwen36-quark-int8-tp4-layerfamily-timing-summary-20260613r.json`
- Eager/no-graph attribution request metrics:
  `data/qwen36-quark-int8-tp4-layerfamily-eager-p512o64-20260613s.json`
- Eager/no-graph attribution timing log:
  `data/qwen36-quark-int8-tp4-layerfamily-eager-20260613s.log`
- Eager/no-graph attribution timing summary:
  `data/qwen36-quark-int8-tp4-layerfamily-eager-summary-20260613s.json`
- Restored accepted endpoint provenance:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-layerfamily-timing-20260613s.json`
- Source patch artifact:
  `patches/vllm-qwen36-layer-family-collective-timing-20260613.patch`

## Graph Path

Command shape:

```bash
LOG_PATH=/tmp/qwen36-quark-int8-tp4-layerfamily-timing-20260613r.log \
VLLM_XPU_DECODE_TIMING_ALLOW=1 \
VLLM_XPU_DECODE_TIMING=1 \
VLLM_XPU_DECODE_TIMING_SYNC=0 \
VLLM_XPU_DECODE_TIMING_SUMMARY=1 \
VLLM_XPU_DECODE_TIMING_STEP_SUMMARY=1 \
VLLM_XPU_DECODE_TIMING_SKIP_FIRST=48 \
VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST=48 \
scripts/launch-qwen36-quark-int8-accepted.sh
```

Request: c1, p512/o128, natural-chat preset, streaming, forced output length.

Endpoint metrics:

- Client output after first chunk: `100.71 tok/s`
- vLLM decode time: `10.01 ms/generated token`
- Client TTFT: `94.26 ms`
- vLLM model-forward step summary: mean `4.43 ms`, median `4.28 ms`

Graph path attribution:

- MoE is the dominant visible model-side family.
- `moe.quant_method_total` is the largest MoE bucket, with rank 3 slowest
  (`avg 1.81 ms/call`, `2379.56 ms` total in the captured summary).
- `xpu_moe.gemm1_w8a8` is strongly rank-skewed in this run: rank 3 total
  `617.78 ms`, while rank 0 total is `35.95 ms`. This needs replay/parity
  confirmation because no-sync timings and one outlier can distort totals, but
  it is the biggest concrete lead.
- `xpu_moe.gemm2_w8a8`, quant stages, activation, remap, and gather are
  visible and much smaller than GEMM1/overall MoE.
- GDN core is consistently visible: `0.047-0.051 ms/call`, `~225-244 ms`
  total per rank in the captured graph summary.
- Logits are small: `~0.219-0.243 ms/step`.
- TP collectives are not the top wall in this trace: all all-reduce labels sum
  to about `136-142 ms` total per rank over the captured window, with the
  biggest shape `all_reduce:(48, 2048):bf16` at about `15-17 ms` total per
  rank.

Important caveat: timing is no-sync and nested. Totals are useful for ranking
where to investigate, not for additive wall-clock accounting.

## Eager Attribution

Command shape:

```bash
LOG_PATH=/tmp/qwen36-quark-int8-tp4-layerfamily-eager-20260613s.log \
XPU_GRAPH=0 \
VLLM_XPU_ENABLE_XPU_GRAPH=0 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=0 \
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0 \
COMPILATION_CONFIG='{}' \
VLLM_EXTRA_ARGS='--enforce-eager' \
VLLM_XPU_DECODE_TIMING_ALLOW=1 \
VLLM_XPU_DECODE_TIMING=1 \
VLLM_XPU_DECODE_TIMING_SYNC=0 \
scripts/launch-qwen36-quark-int8-accepted.sh
```

Request: c1, p512/o64, natural-chat preset, streaming, forced output length.

Endpoint metrics:

- Client output after first chunk: `10.52 tok/s`
- vLLM decode time: `96.54 ms/generated token`
- Client TTFT: `200.38 ms`

The eager run is diagnostic-only, but it exposes Python-level family labels:

- `qwen3_next.layer_type.linear_attention`: max-rank total `5450.58 ms`,
  mean rank avg `2.19 ms/call`.
- `qwen3_next.layer.mlp`: max-rank total `3377.10 ms`, mean rank avg
  `1.01 ms/call`.
- `qwen3_next.moe.experts_internal_router`: max-rank total `3292.37 ms`,
  mean rank avg `0.99 ms/call`.
- `qwen3_next.layer_type.full_attention`: max-rank total `2690.24 ms`,
  mean rank avg `3.22 ms/call`.
- Full-attention rotary and norms are visible in eager and look nontrivial
  there, but this is not enough to supersede the graph-path MoE decision.

## Decision

Promote the next engineering step to the persistent W8A8 MoE layerlet path.

Reason:

- In the accepted graph path, collectives are measurable but not the largest
  visible wall.
- MoE quant/application buckets dominate the all-rank summary.
- The biggest actionable skew is inside the W8A8 MoE path, especially GEMM1 on
  rank 3 in this trace.

Collective-only replay remains on the list, but it is now secondary unless the
MoE replay shows the graph timing was misleading.

## Next Work

1. Build a one-layer/rank W8A8 MoE replay fixture from the current accepted
   graph path.
2. Reproduce the rank-skewed GEMM1 observation outside vLLM scheduling.
3. Keep expert pointers, scales, scratch, route buffers, and output buffers
   resident.
4. Measure route/remap, quant, GEMM1, activation, quant2, GEMM2, gather/combine
   in the replay fixture with exact parity.
5. If the replay confirms the wall, prototype the persistent W8A8 layerlet.
6. Only after replay parity and layer target are met, run endpoint A/B and the
   standard quality/reliability gates.

## Continuation: MoE Sidecar Readiness

The first follow-up kept the persistent W8A8 MoE path as primary and recorded
the existing oneDNN replay evidence in
`notes/2026-06-13-qwen36-moe-sidecar-readiness.md`.

Small source-readiness patch:
`patches/vllm-xpu-qwen36-onednn-sidecar-end-offsets-20260613.patch`.
The helper `_make_onednn_grouped_offsets` now emits cumulative end offsets,
matching oneDNN grouped memory and the exact standalone oneDNN runner. Smoke:
`data/qwen36-onednn-sidecar-offset-helper-smoke-20260613.json`.

Next implementation move: add a disabled-by-default C++ sidecar execution op
for one live grouped GEMM, prove exact parity outside endpoint mutation, then
grow it into a resident two-GEMM/full-island replay before any endpoint A/B.
