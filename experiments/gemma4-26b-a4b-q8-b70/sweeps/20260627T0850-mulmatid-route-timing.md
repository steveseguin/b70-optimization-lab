# 2026-06-27T08:50Z MUL_MAT_ID Route Timing Diagnostic

## Question

Is there still a meaningful fresh-decode win in the routed MoE plumbing
around `ggml_sycl_mul_mat_id()` for the current Gemma 4 26B Q8 record stack,
or is the path now dominated by the actual expert matmul?

This was prompted by the current valid record:

- run: `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/`
- fresh row0 after TTFT: `104.30919255569083 tok/s`
- canary: `6144/6144`
- LocalMaxxing: `cmqw1tgzx0366qr01g4lkv7f1`

## Diagnostic Patch

Added default-off timing instrumentation to
`/home/steve/src/llama.cpp-gemma-record-stack/ggml/src/ggml-sycl/ggml-sycl.cpp`
behind:

- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_TIMING=1`
- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_TIMING_EVERY=<N>` (default `25`; diagnostic
  used `8`)

The timing path inserts `stream->wait()` around route-copy/sort, map upload,
gather, matmul, and scatter phases. Therefore throughput from this run is
**not headline-valid** and must not be compared as a record attempt. It is only
phase attribution.

Harness identity capture was updated so both timing flags are recorded in:

- `scripts/run-gemma4-26b-first-baseline.sh`
- `scripts/run-gemma4-26b-llamacpp-replica.sh`

## Run

- run: `data/gemma4-q8-gpu0-mmid-route-timing-rmsreuse-ub768-nmin3-pmin010-20260627T085044Z/`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-mmid-route-timing-rmsreuse-ub768-nmin3-pmin010-20260627T085044Z.server.log`
- parsed summary:
  `data/gemma4-q8-gpu0-mmid-route-timing-rmsreuse-ub768-nmin3-pmin010-20260627T085044Z/route-timing-summary.json`
- identity: current record RMS-reuse stack, `UBATCH_SIZE=768`,
  `MTP_N_MIN=3`, `MTP_P_MIN=0.10`, route cache on, router post-scale off
- diagnostic depth: `CANARY_REPEATS=2`, `BENCH_REPEATS=1`,
  `MAX_TOKENS=128`
- canary: `8/8`
- timing records parsed: `337`

Perturbed throughput was `93.17246386435396 tok/s` after TTFT, but this is
expectedly lower because the diagnostic adds waits and should not be treated as
a speed result.

## Timing Summary

Most relevant decode-like group:

| Group | Samples | Total mean | Matmul mean | Route overhead mean | Route pct | Matmul pct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `n_tokens=8 src0=q8_0` | 231 | `651.43 us` | `630.77 us` | `20.66 us` | `3.30%` | `96.70%` |
| `n_tokens=2 src0=q8_0` | 14 | `272.86 us` | `254.43 us` | `18.43 us` | `6.92%` | `93.08%` |
| `n_tokens=5 src0=q8_0` | 7 | `597.71 us` | `577.57 us` | `20.14 us` | `3.38%` | `96.62%` |

Prefill / larger-token groups are even more matmul-dominated:

| Group | Samples | Total mean | Matmul mean | Route overhead mean | Route pct | Matmul pct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `n_tokens=36 src0=q8_0` | 14 | `1364.93 us` | `1330.21 us` | `34.71 us` | `2.64%` | `97.36%` |
| `n_tokens=38 src0=q8_0` | 28 | `1369.50 us` | `1333.07 us` | `36.43 us` | `2.71%` | `97.29%` |
| `n_tokens=39 src0=q8_0` | 14 | `1542.21 us` | `1504.29 us` | `37.93 us` | `2.50%` | `97.50%` |
| `n_tokens=587 src0=q8_0` | 7 | `3027.86 us` | `2614.86 us` | `413.00 us` | `13.73%` | `86.27%` |

The full group table is in `route-timing-summary.json`.

## Decision

Stop treating `MUL_MAT_ID` route/gather/scatter plumbing as the lead fresh
decode optimization lane for the current record stack. The record-relevant
decode path is dominated by expert matmul, not route setup:

- route overhead is usually only `~18-21 us` for decode-like samples;
- the profiled matmul body is `~93-97%` of the path;
- even eliminating all measured route overhead would be only a few percent,
  and prior route-cache / direct / grouped / per-slot attempts already failed
  to beat the record.

The next material lane should be verifier/output economics:

- current record avoids full logits host transfer, but still computes the full
  target LM-head matmul;
- subagent audit points to an exact candidate-vs-max verifier op or other
  narrow output shortcut as the only plausible remaining large win;
- any such change must preserve fresh-response validity and greedy verifier
  exactness, and must fall back for grammar/logit-bias/non-greedy cases.
