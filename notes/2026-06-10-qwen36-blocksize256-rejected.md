# Qwen3.6 INT8 Block Size 256 Rejection

Date: 2026-06-10

## Context

After accepting `--no-enable-prefix-caching` as the current Qwen3.6 INT8
runtime speed candidate, I tested one more quality-neutral runtime knob:
`--block-size 256`.

Everything else stayed unchanged:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- runtime dtype: BF16
- quantization: Quark W8A8 INT8
- tensor parallelism: TP4
- context cap: 32K
- XPU PIECEWISE graph capture
- clone-safe custom-op all-reduce collectives
- prefix caching disabled

## Runtime Behavior

The default restored no-prefix run reports:

- effective KV cache block size: `64` for XPU FlashAttention
- effective attention block size: `576`
- mamba page padding: `9.92%`
- GPU KV cache size: `2,052,915` tokens
- max 32K concurrency estimate: `62.65x`

The `--block-size 256` candidate reports:

- requested block size: `256`
- effective attention block size: `768`
- mamba page padding: `46.56%`
- GPU KV cache size: `2,008,108` tokens
- max 32K concurrency estimate: `61.28x`

So this flag does not improve capacity for this hybrid architecture on the
current XPU FlashAttention path. It increases padding and slightly reduces the
reported KV-token capacity.

## Single Request Result

p512/n512 streaming, eight repeats:

| metric | no-prefix baseline | block-size 256 |
| --- | ---: | ---: |
| corrected output tok/s after first chunk | `98.0404` | `98.2140` |
| output tok/s end-to-end | `96.7747` | `96.9147` |
| mean client TTFT | `77.74 ms` | `80.08 ms` |

Artifacts:

- baseline: `data/qwen36-quark-int8-tp4-noprefix-graph32k-single-confirm-20260610.json`
- candidate: `data/qwen36-quark-int8-tp4-noprefix-block256-graph32k-single-20260610.json`

The small speed delta is within noise and TTFT is worse, so this is not a
meaningful single-request improvement.

## Aggregate Result

Frontdoor p512/n256 sweep:

| concurrency | no-prefix wall tok/s | block-size 256 wall tok/s | no-prefix from-first tok/s | block-size 256 from-first tok/s |
| --- | ---: | ---: | ---: | ---: |
| 1 | `95.94` | `96.19` | `99.02` | `99.06` |
| 2 | `170.19` | `173.33` | `181.10` | `178.05` |
| 4 | `307.85` | `154.90` | `316.24` | `156.84` |
| 8 | `553.27` | `540.37` | `566.10` | `552.59` |
| 16 | `851.63` | `888.30` | `868.43` | `904.71` |
| 32 | `1397.95` | `1371.35` | `1419.06` | `1391.36` |
| 48 | `1700.89` | `1533.55` | `1727.50` | `1550.27` |

Artifacts:

- baseline: `data/qwen36-quark-int8-tp4-noprefix-graph32k-concurrency-20260610.json`
- candidate: `data/qwen36-quark-int8-tp4-noprefix-block256-graph32k-concurrency-20260610.json`

The candidate regresses the c48 service target by about `9.8%` wall throughput.
It also has an unstable c4 result with mean TTFT near `2.8 s`.

## Decision

Reject `--block-size 256` for this Qwen3.6 INT8 stack. Keep the default XPU
FlashAttention-selected KV block size (`64`) and effective attention block size
(`576`) unless a later candidate proves otherwise.

This result reinforces that the next speed work should target graph and kernel
boundaries in the decode path, not coarse KV page sizing.
