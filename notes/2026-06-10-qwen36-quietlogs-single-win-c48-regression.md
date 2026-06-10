# Qwen3.6 INT8 Quiet Logs Single-Request Win With C48 Variance Check

Date: 2026-06-10

## Context

I tested the accepted Qwen3.6 INT8 no-prefix runtime with server logging noise
reduced:

- `--disable-log-stats`
- `--disable-uvicorn-access-log`

The intent was to reduce host-side noise during streaming requests without
changing model weights, quantization, sampling math, tensor parallelism, graph
capture, or request scheduling.

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
- default stream interval `1`

## Single Request Result

p512/n512 streaming, eight repeats:

| metric | no-prefix baseline | quiet logs |
| --- | ---: | ---: |
| corrected output tok/s after first chunk | `98.0404` | `98.7351` |
| output tok/s end-to-end | `96.7747` | `97.4968` |
| total client tok/s | `194.6544` | `194.9937` |
| mean client TTFT | `77.74 ms` | `75.99 ms` |

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-quietlogs-graph32k-single-20260610.json`

The single-request result is cleaner than the accepted profile:

- corrected after-first min/max: `97.96` / `99.17 tok/s`
- e2e min/max: `96.79` / `97.94 tok/s`
- mean TTFT improved by about `1.75 ms`

## Quality

The frontdoor quality suite passed with full baseline parity:

- exact canaries: pass
- compact JSON semantics: pass
- repeat stability: pass
- 8K-class long-context needle recall: pass
- `baseline_match_all`: `true`

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-quietlogs-frontdoor-quality-20260610.json`

## Aggregate Throughput

Frontdoor p512/n256 concurrency sweep:

| concurrency | accepted wall tok/s | quiet wall tok/s | accepted from-first tok/s | quiet from-first tok/s |
| --- | ---: | ---: | ---: | ---: |
| 1 | `95.94` | `96.48` | `99.02` | `99.68` |
| 2 | `170.19` | `174.31` | `181.10` | `185.63` |
| 4 | `307.85` | `312.88` | `316.24` | `322.29` |
| 8 | `553.27` | `533.42` | `566.10` | `545.19` |
| 16 | `851.63` | `949.83` | `868.43` | `968.31` |
| 32 | `1397.95` | `1383.61` | `1419.06` | `1404.55` |
| 48 | `1700.89` | `1545.65` | `1727.50` | `1564.93` |

Artifacts:

- accepted: `data/qwen36-quark-int8-tp4-noprefix-graph32k-concurrency-20260610.json`
- quiet logs: `data/qwen36-quark-int8-tp4-noprefix-quietlogs-graph32k-concurrency-20260610.json`

I reran quiet-logs c48 with a separate prompt salt because the first c48 result
was materially below the earlier accepted c48 reference:

- wall: `1517.63 tok/s`
- from-first: `1539.37 tok/s`

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-quietlogs-c48-confirm-20260610.json`

## Accepted C48 Refresh

After restoring the accepted no-prefix runtime, I reran c48 with a fresh prompt
salt to separate a true quiet-logs regression from current-state variance after
many runtime restarts:

- accepted c48 refresh wall: `1479.66 tok/s`
- accepted c48 refresh from-first: `1495.39 tok/s`
- mean TTFT: `1.55 s`

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-accepted-c48-refresh-20260610.json`

This accepted refresh is lower than both quiet-logs c48 measurements
(`1545.65` / `1564.93` and `1517.63` / `1539.37`). Therefore the c48 drop from
the historical accepted reference (`1700.89` / `1727.50`) should not be
attributed to quiet logs alone. High-concurrency throughput is currently
variable after many endpoint restarts and needs repeated A/B or a longer
steady-state reliability run before production promotion.

## Decision

Keep quiet-logs as a quality-safe single-request and low/mid-concurrency
candidate. It is a valid single-request speed candidate and likely worth a
production-profile A/B.

The current priority is single-request speed, and this is a real improvement
there. However, production default promotion still needs repeated aggregate and
reliability checks because the c48 result is volatile in the current lab state
and logging changes reduce some runtime observability.

The accepted no-prefix runtime was restored after the screen:

- session: `qwen36-tp4-noprefix-32k`
- backend `/health`: pass
- backend `/v1/completions`: pass, returned `OK` after the raw thinking wrapper
- frontdoor `/v1/chat/completions`: pass, returned exactly `OK`
