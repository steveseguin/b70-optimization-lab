# Qwen3.6 INT8 No-Prefix Runtime Win

Date: 2026-06-10

## Context

After refreshing the accepted TP4 32K baseline, I tested runtime-only changes
that keep the same model, quantization, dtype, kernels, and 32K context cap.

The goal was to improve single-request decode speed without changing quality.

## Baseline

Accepted TP4 prefix-caching baseline after restart:

- Corrected output tok/s after first chunk: `94.1263`
- Output tok/s end-to-end: `93.0006`
- Mean client TTFT: `76.46 ms`
- Artifact: `data/qwen36-quark-int8-graph32k-single-refresh-20260610.json`

## Rejected Screens

### TP4 `max_num_seqs=1`, `max_num_batched_tokens=1024`

Result:

- Corrected output tok/s after first chunk: `85.1122`
- Output tok/s end-to-end: `84.1795`
- Mean client TTFT: `75.90 ms`
- Artifact: `data/qwen36-quark-int8-seq1-mbt1024-single-20260610.json`

The median repeats were baseline-like, but the first measured p512/n512 repeat
fell to about `57.7 tok/s`. This profile did not improve steady-state speed and
introduced worse measured stability, so reject it.

### TP2, 32K, `max_num_batched_tokens=8192`

Result:

- Corrected output tok/s after first chunk: `86.8477`
- Output tok/s end-to-end: `85.8091`
- Mean client TTFT: `82.87 ms`
- Artifact: `data/qwen36-quark-int8-tp2-graph32k-single-20260610.json`

TP2 fit the model and preserved the 32K cap, with `16.88 GiB` model memory per
active GPU and `31.92x` reported max concurrency for 32K requests. It was slower
than TP4, so tensor-parallel communication is not the main single-request limiter
for this model on this stack.

## Accepted Screen: TP4 With Prefix Caching Disabled

Runtime change:

- Remove `--enable-prefix-caching`
- Add `--no-enable-prefix-caching`
- Keep TP4, 32K, Quark W8A8 INT8, BF16 runtime, XPU PIECEWISE graph, native XPU
  INT8 dense/MoE kernels, and clone-safe custom-op all-reduce unchanged.

Initial p512/n512 four-repeat result:

- Corrected output tok/s after first chunk: `97.9188`
- Output tok/s end-to-end: `96.6770`
- Mean client TTFT: `77.37 ms`
- Artifact: `data/qwen36-quark-int8-tp4-noprefix-graph32k-single-20260610.json`

Confirmation p512/n512 eight-repeat result:

- Corrected output tok/s after first chunk: `98.0404`
- Output tok/s end-to-end: `96.7747`
- Mean client TTFT: `77.74 ms`
- Artifact: `data/qwen36-quark-int8-tp4-noprefix-graph32k-single-confirm-20260610.json`

Delta versus restart baseline:

- Corrected after-first output speed: `+4.16%`
- End-to-end output speed: `+4.06%`

## Quality

Matched-route quality through the LAN frontdoor passed:

- exact canaries,
- JSON field semantics,
- 8-repeat hash stability,
- 8K-class long-context needle recall,
- full baseline hash/normalized-output parity.

Artifact: `data/qwen36-quark-int8-tp4-noprefix-frontdoor-quality-20260610.json`

Important test lesson: the direct backend quality run failed because it bypassed
the frontdoor chat-template kwargs that set `enable_thinking:false`. The raw
backend emitted "thinking process" text and failed exact canaries. That direct
backend artifact is kept only as a route-mismatch diagnostic:

- `data/qwen36-quark-int8-tp4-noprefix-quality-20260610.json`

For chat quality comparisons, use the same route as the baseline unless the
request explicitly includes equivalent chat-template kwargs.

## Aggregate Throughput

Frontdoor p512/n256 concurrency sweep:

| concurrency | baseline wall tok/s | no-prefix wall tok/s | baseline from-first tok/s | no-prefix from-first tok/s |
| --- | ---: | ---: | ---: | ---: |
| 1 | `92.32` | `95.94` | `95.08` | `99.02` |
| 2 | `162.80` | `170.19` | `167.04` | `181.10` |
| 4 | `303.04` | `307.85` | `310.98` | `316.24` |
| 8 | `538.09` | `553.27` | `550.64` | `566.10` |
| 16 | `888.51` | `851.63` | `904.45` | `868.43` |
| 32 | `1408.86` | `1397.95` | `1433.30` | `1419.06` |
| 48 | `1604.00` | `1700.89` | `1622.33` | `1727.50` |

Artifact: `data/qwen36-quark-int8-tp4-noprefix-graph32k-concurrency-20260610.json`

The aggregate result is mixed in the middle of the sweep but positive at c48,
and the single-request result is the clearest gain. Shared-prefix/cache-hit
workloads still need a separate A/B before using no-prefix as the final
production default.

## Current Decision

Accept `--no-enable-prefix-caching` as the current speed candidate for unique
prompt / single-request decode work. Do not claim this solves the larger target:
the confirmed single-request speed is still only about `98 tok/s`, far below the
`>200 tok/s` goal. The next gains still require decode-path work around dense
RMS/quant/GEMM boundaries, MoE epilogues, or graph/custom-op boundaries.
