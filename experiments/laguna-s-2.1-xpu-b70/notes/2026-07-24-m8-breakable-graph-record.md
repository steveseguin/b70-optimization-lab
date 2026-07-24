# Laguna S 2.1 exact Breakable graph record

Date: 2026-07-24 America/Toronto

Status: **VERIFIED RECORD CANDIDATE**. The conservative lower graph start is
`92.16352215694299 tok/s`, compared with the approved
`33.89498511171744 tok/s` record.

## Result

The preregistered fresh-service A1/B1/B2/A2 campaign passed every quality,
honesty, causal, reproducibility, and record gate:

| Leg | Treatment | Median tok/s, tokens 1-100 after TTFT | Canonical exact | Cached tokens |
|---|---|---:|---:|---:|
| A1 | eager | 34.49116381990456 | 13/13 | 0 on 13/13 |
| B1 | Breakable graph | 92.76071675369911 | 13/13 | 0 on 13/13 |
| B2 | Breakable graph | **92.16352215694299** | 13/13 | 0 on 13/13 |
| A2 | eager | 34.591122672009526 | 13/13 | 0 on 13/13 |

The submitted value is the lower B start. It improves the prior approved
record by `58.26853704522555 tok/s` (`+171.90902091614203%`, or
`2.71909020916142x`).

Both adjacent comparisons passed the preregistered causal gates:

| Pair | Graph row wins | Median paired gain | Decode-cycle saving | Acceptance drift |
|---|---:|---:|---:|---:|
| B1 vs A1 | 13/13 | +169.42082090615466% | 55.0490377685078 ms | 0.0003070338847266929 |
| B2 vs A2 | 12/13 | +169.36519273519548% | 54.22048225686592 ms | 0.0003066772832345799 |

All four legs are mutually bitwise identical and match the canonical q1
greedy teacher. Long-then-next passed on every leg, as did the 863-token
rollover row. Metrics started at zero, each leg recorded exactly 13 decode
requests, and every service used a private cache and RPC path.

## What changed

The candidate retains the approved exact DFlash7, fused W1-route-W2,
route-interleaved expert GEMM, shared-elementwise, QKNorm/RoPE, and W1 N64
stack. The only treatment difference from eager is the validated production
Breakable graph runtime:

```text
mode=NONE
cudagraph_mode=PIECEWISE
cudagraph_capture_sizes=[8]
max_cudagraph_capture_size=8
VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=1
VLLM_USE_BREAKABLE_CUDAGRAPH=1
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
```

Each graph start performed its first lazy capture inside the first measured
cold request. Each logged exactly one audited capture and one replay on ranks
0 through 3, with 146 graph segments and 145 eager breaks. The eager controls
logged no graph capture or replay.

No warm-up generation, retry, prefix cache, history/ngram acceleration,
response reuse, context checkpoint, qualification timing, or prior-run output
was used.

## Frozen identity

- main campaign tooling:
  `4b4b5dd9c81d7b85819d3c93d65cb1a1f69e4363`;
- vLLM:
  `0ce373a3115fb4498c5e7a041d4fc9212fd6b5ca`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`; and
- hardware: four Intel Arc Pro B70, TP4/EP4, one active generation.

Models, caches, RPC state, and evidence all used internal NVMe paths.

## Sealed evidence

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-formal-graph-crossover-4b4b5dd9c-0ce373a31-20260724T220518Z
```

The root and leg directories are mode `0500`; evidence files are mode `0400`.

Key SHA256:

```text
f8f2697ce6abcde7a78d9af2a16f89628027ef55a3a60e8d60b025e31c135378  full-analysis.json
9467b3d105a918180fb3e92e6b951f4217a5fc285df0a939d14ecfad1a456852  all-vs-teacher.json
f2ea7649923f47e8e0e3c4230c56fc7a7926157f24f981a91718eeed65a6248f  cross-leg.json
616445a0996ec2795bed130d3dc9c79261ae4b9fd3c36d5583c040df22efdebc  B2-graph/bench.json
393d2ea3c29328cae249df4b2a101ee30689d9b7d3ca4eddf06eef49a146c3d9  B2-graph/exactness-vs-q1.json
3342886132977e73782046fcc9b1fb78efcfb8b4e12cd2f448e564447074792a  B2-graph/server.log
```

Two independent read-only audits recomputed raw token equality, cache-zero
status, all performance statistics, metrics deltas, topology, environment,
26 idle snapshots per leg, cleanup, sealing, and provenance. Both reported no
discrepancy.

## Decision

Promote the exact Breakable graph stack. Submit only
`92.16352215694299 tok/s`, the lower graph start, after the LocalMaxxing
payload passes its independent preflight. Preserve both graph starts and both
controls as the reproducibility record.
