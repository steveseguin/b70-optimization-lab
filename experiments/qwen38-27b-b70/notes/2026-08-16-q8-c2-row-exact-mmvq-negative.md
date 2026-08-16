# Qwen3.8 Q8 c2 row-exact MMVQ split: quality negative

Date: 2026-08-16  
Disposition: rejected; do not promote

## Hypothesis

The accepted c2 endpoint uses a two-column Q8 MMVQ kernel when two decode rows
are batched. Its greedy output is exact for fixed prompt pair 0/1 but differs
from same-slot sequential oracles for disjoint pair 2/3. This candidate forced
Q8 `ne[1] == 2` through the existing no-copy row splitter at `1 + 1`, causing
each row to use the same single-column MMVQ arithmetic as sequential decode.

The change was opt-in through `GGML_SYCL_MMVQ_SPLIT_Q8_C2=1`. Control and
treatment used the same freshly built binary. The full patch is retained in
[`q8-c2-row-exact-mmvq-quality-negative-20260816.diff`](../patches/q8-c2-row-exact-mmvq-quality-negative-20260816.diff).

## Result

| Fixed prompt pair | Door | Aggregate conventional | Exact to sequential oracle |
| --- | --- | ---: | ---: |
| 0/1 | off | `56.158854 tok/s` | 2/2 |
| 0/1 | on | `57.430603 tok/s` | 2/2 |
| 2/3 | off | `55.904127 tok/s` | 0/2 |
| 2/3 | on | `56.990979 tok/s` | 0/2 |

Every request was cache-cold. The treatment improved aggregate throughput by
`2.265%` on pair 0/1 and `1.944%` on pair 2/3, but it did not fix the decisive
quality gate. Pair 2/3 still differed in both slots. The Q8 two-column MMVQ
reduction order is therefore not the sole source of schedule-dependent output.

The binary ended with `VERIFY_MISMATCH=0`; both cards returned to normal idle
state and the current boot log contained no new Xe fault, reset, hang,
device-lost, or CAT error.

## Reproduction identity

- base source: mndodd `intel-sycl-optimization`, commit
  `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`, plus the accepted Qwen3.8 Q8 TP2
  patch stack;
- `llama-server` SHA-256:
  `d02284709d3fbb6c53851fc6b793e80606a7bef324b216bb7674ab875df2cd2a`;
- model SHA-256:
  `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`;
- server: TP2 `1/1`, `--parallel 2`, `--ctx-size 16384`, `-b 1024`,
  `-ub 256`, F16 KV, flash attention, reasoning off, no speculation;
- build: Release, oneAPI 2026.1, BMG-G31 AOT, DNN/graph/host fallback off;
- capture: cache-cold fixed-slot sequential oracles followed by two
  barrier-synchronized 256-token streams.

Structured results and raw-file hashes are in
[`2026-08-16-q8-c2-row-exact-mmvq-negative.json`](../data/2026-08-16-q8-c2-row-exact-mmvq-negative.json).

## Decision

Do not use this patch in a quality-preserving reproduction package. It is a
small c2 speed improvement, but the arbitrary-prompt quality problem remains.
Any next c2 quality investigation must isolate other batched arithmetic (for
example attention, recurrent-state, normalization, or fused elementwise paths)
rather than repeat the Q8 MMVQ-only split.
