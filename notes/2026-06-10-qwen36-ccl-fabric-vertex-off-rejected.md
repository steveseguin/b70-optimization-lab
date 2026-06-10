# Qwen3.6 INT8 CCL Fabric Vertex Override Rejection

Date: 2026-06-10

## Context

I tested `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0` on the accepted
Qwen3.6 INT8 no-prefix runtime.

The intent was to see whether bypassing oneCCL's fabric vertex connection
check would reduce collective setup or replay overhead without changing model
math.

Everything else stayed unchanged:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- runtime dtype: BF16
- quantization: Quark W8A8 INT8
- tensor parallelism: TP4
- context cap: 32K
- XPU PIECEWISE graph capture
- clone-safe custom-op all-reduce collectives
- prefix caching disabled
- `--max-num-batched-tokens 8192`
- `--max-num-seqs 48`

The runtime log confirmed that oneCCL accepted the override:
`CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK changed to be 0 (default:1)`.

## Single Request Result

p512/n512 streaming, eight repeats:

| metric | no-prefix baseline | fabric vertex off |
| --- | ---: | ---: |
| corrected output tok/s after first chunk | `98.0404` | `98.2247` |
| output tok/s end-to-end | `96.7747` | `96.9361` |
| mean client TTFT | `77.74 ms` | `79.47 ms` |

Artifacts:

- baseline: `data/qwen36-quark-int8-tp4-noprefix-graph32k-single-confirm-20260610.json`
- candidate: `data/qwen36-quark-int8-tp4-noprefix-cclfabric0-graph32k-single-20260610.json`

The single-request delta is within noise and TTFT is worse, so this does not
clear the promotion bar.

## Aggregate Result

Frontdoor p512/n256 sweep:

| concurrency | no-prefix wall tok/s | fabric vertex off wall tok/s | no-prefix from-first tok/s | fabric vertex off from-first tok/s |
| --- | ---: | ---: | ---: | ---: |
| 1 | `95.94` | `96.44` | `99.02` | `99.32` |
| 2 | `170.19` | `175.00` | `181.10` | `179.81` |
| 4 | `307.85` | `154.09` | `316.24` | `156.01` |
| 8 | `553.27` | `555.02` | `566.10` | `570.73` |
| 16 | `851.63` | `865.09` | `868.43` | `881.05` |
| 32 | `1397.95` | `1367.36` | `1419.06` | `1392.31` |
| 48 | `1700.89` | `1635.20` | `1727.50` | `1657.14` |

Artifacts:

- baseline: `data/qwen36-quark-int8-tp4-noprefix-graph32k-concurrency-20260610.json`
- candidate: `data/qwen36-quark-int8-tp4-noprefix-cclfabric0-graph32k-concurrency-20260610.json`

The candidate regresses c48 wall throughput by about `3.9%` and shows another
bad c4 run with mean TTFT near `2.8 s`.

## Decision

Reject `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0` for this Qwen3.6 INT8
runtime. Keep the oneCCL default.

This result matches the MiniMax lesson from earlier: this oneCCL fabric knob is
not a reliable latency win on the B70 TP4 stack, and it should not be promoted
without a repeatable endpoint-level gain.
