# Qwen3.6 Quark INT8 TP2 Graph32K Rejection

Date: 2026-06-10

## Context

I checked whether reducing tensor-parallel degree could improve single-request
decode by cutting the TP4 collective count. The existing artifact already covers
the relevant topology for the current model:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Runtime family: Quark W8A8 INT8, BF16 runtime, XPU graph, 32K context
- Topology candidate: TP2 graph32K
- Speed shape: p512/n512 single request
- Artifact: `data/qwen36-quark-int8-tp2-graph32k-single-20260610.json`

## Result

TP2 graph32K:

- Corrected output tok/s after first chunk: `86.8477`
- Output tok/s end-to-end: `85.8091`
- Total client tok/s: `171.6181`
- Mean client TTFT: `82.8723 ms`

Current TP4 no-prefix control:

- Corrected output tok/s after first chunk: `99.6301`
- Output tok/s end-to-end: `98.3908`
- Total client tok/s: `196.7815`
- Mean client TTFT: `74.7738 ms`
- Artifact: `data/qwen36-quark-int8-tp4-noprefix-current-control-continue-20260610.json`

## Decision

Reject TP2 graph32K for the current 35B Quark INT8 path. Fewer TP ranks do not
offset the larger per-rank work and lower parallelism for batch-1 decode. Keep
TP4 as the accepted single-session speed topology.

Next work should stay on TP4 and target source-level forward-graph costs rather
than topology-only launch changes.
