# 2026-06-29 Gemma4 Q8 Regular-MMVQ Top1 Partial Reduction: Negative

## Purpose

The first regular-Q8 LM-head top1 epilogue prototype replaced part of the
verifier LM-head path, but still left
`MUL_MAT_ARGMAX:spec_verify_regular_mmvq_top1_epilogue_token_rows` as the
hottest node at about `1.325 ms/call`. The suspected issue was a single global
top1 slot per output row causing excessive atomic/reduction contention.

This experiment added a default-off second version:

- `LLAMA_SPEC_VERIFY_REGULAR_MMVQ_TOP1_EPILOGUE=1`
- `LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE=1`
- `LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE_PARTIAL=1`

The v2 design writes per-workgroup partial top1 candidates, then runs a final
reduction over those partials. It preserves the same top1 tie-breaking as the
v1 packed-score path but avoids every workgroup atomically fighting over one
row-level best slot.

## Source Artifacts

Source tree tested:
`/home/steve/src/llama.cpp-gemma-record-repro-c926`, detached at
`c926ad098` with the dirty Gemma optimization stack.

Patch snapshots:

- before this lane:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260629-llamacpp-current-stack-before-top1partial.patch`
- current files after the v2 attempt:
  `patches/gemma4-26b-a4b-q8-b70/20260629-regular-mmvq-top1-partial-experiment-current-files.patch`

Touched source files:

- `ggml/src/ggml-sycl/mmvq.hpp`
- `ggml/src/ggml-sycl/mmvq.cpp`
- `ggml/src/ggml-sycl/ggml-sycl.cpp`

The harness scripts were also updated to pass and echo
`LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE_PARTIAL` so future run artifacts preserve the
flag identity. The v2 run's external server log confirms
`LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE_PARTIAL=1`; the JSON summary did not yet
include that key before this harness identity update.

## Validation Screen

All rows below use the fixed realistic cold suite with `cached_tokens=0`, each
prompt once, no prefix/KV/history reuse, and the strict128 screen
(`MAX_TOKENS=128`, `CANARY_REPEATS=64`). All three passed the fixed gate and
256 canary rows, so this is a performance loss, not a quality failure.

| Run | Primary median tok/s, tokens 1-100 after TTFT | p10 | mean | Full tok/s after TTFT | Wall full tok/s | TTFT median ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 116.818876 | 102.086982 | 115.473145 | 113.988711 | 97.810605 | 180.171 |
| top1 v1 | 114.478474 | 104.883551 | 115.085818 | 111.769265 | 94.454910 | 180.525 |
| top1 v2 partial | 107.095281 | 99.896476 | 108.591926 | 106.711451 | 93.418314 | 179.907 |

Run directories:

- `data/gemma4-q8-gpu0-top1partial-control-strict128-20260629Tscreen`
- `data/gemma4-q8-gpu1-top1partial-v1-strict128-20260629Tscreen`
- `data/gemma4-q8-gpu2-top1partial-v2-strict128-20260629Tscreen`

## Decision

Closed negative. The partial-reduction redesign made the primary metric worse:

- v2 partial vs control: `107.095281` vs `116.818876 tok/s` (`-8.3%`)
- v2 partial vs v1: `107.095281` vs `114.478474 tok/s` (`-6.4%`)
- v2 partial remains below the current valid full512 record
  `115.8466634928202 tok/s`.

Likely explanation: the extra partial-buffer writes, final-reduce kernel, and
local-memory/reduction overhead outweigh any reduction in row-level contention
for this verifier shape. Do not run a full512 promotion for this route and do
not submit it to LocalMaxxing.

## Follow-Up

Do not reopen the regular-Q8 LM-head epilogue path without a different design
that removes the remaining top hot node rather than reshaping its reduction
work. The next credible source lane is not the dense/shared BF16 FFN path
unless a future profile shows it as hot. Current profile evidence points at the
final-layer routed MoE BF16 `ffn_moe_gate_up-29` path instead; that should be a
tiny correctness/perf harness first, not another full server warmup.
