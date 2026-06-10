# Qwen3.6 INT8 Stream Interval 8 Rejection

Date: 2026-06-10

## Context

I tested `--stream-interval 8` on the accepted Qwen3.6 INT8 no-prefix runtime.

The intent was to reduce host-side streaming overhead without changing model
weights, quantization, sampling math, tensor parallelism, or graph-captured
model execution. This is a quality-preserving runtime knob, but it changes when
tokens are emitted to streaming clients, so the end-to-end rate and TTFT matter
more than a raw after-first-stream-chunk number.

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

The startup log confirmed async scheduling stayed enabled and graph capture
used the same 15 capture sizes as the accepted runtime.

## Single Request Result

p512/n512 streaming, eight repeats:

| metric | no-prefix baseline | stream interval 8 |
| --- | ---: | ---: |
| corrected output tok/s after first chunk | `98.0404` | `97.5046` |
| output tok/s end-to-end | `96.7747` | `96.2649` |
| total client tok/s | `194.6544` | `192.5297` |
| mean client TTFT | `77.74 ms` | `77.81 ms` |

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-streamint8-graph32k-single-20260610.json`

The slowest repeat was also worse than the accepted profile:

- corrected after-first: `91.5749 tok/s`
- end-to-end: `90.5219 tok/s`

The benchmark emitted 65 streamed text chunks for 512 output tokens, so the
server-side stream interval setting did buffer output, but the reduced stream
event count did not translate into better single-request throughput.

## Decision

Reject `--stream-interval 8` for the current Qwen3.6 INT8 runtime.

Keep the default stream interval of `1`. It preserves lower streaming latency
and is faster on both corrected after-first and end-to-end output-token rates.

## Restore

I restored the accepted no-prefix runtime after the screen:

- session: `qwen36-tp4-noprefix-32k`
- backend `/health`: pass
- backend `/v1/completions`: pass, returned `OK` after the raw thinking wrapper
- frontdoor `/v1/chat/completions`: pass, returned exactly `OK`
