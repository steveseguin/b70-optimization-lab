# Gemma 4 26B A4B Q8: Adaptive Bonus-Row Screen

Date: 2026-06-29

Status: **closed negative**. Do not promote or full512-confirm this lane unless
the design changes materially.

## Question

Can the verifier skip the final bonus output row adaptively after seeing that a
request has a low full-draft acceptance rate, while keeping exact target
verification?

The patch is default-off and adds:

- `LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_ROW`;
- `LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_WARMUP`;
- `LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_MIN_FULL_ACCEPT`.

Patch snapshots:

- `patches/gemma4-26b-a4b-q8-b70/20260629-adaptive-bonus-row-current-stack-server-context.patch`
  - current dirty llama.cpp Gemma stack snapshot; not an isolated upstream PR.
- `patches/gemma4-26b-a4b-q8-b70/20260629-adaptive-bonus-row-harness-identity.patch`
  - harness identity capture for the adaptive env vars.

## Screen

Run timestamp: `20260629T200736Z`

Benchmark class: strict128 realistic cold gate. This is valid for diagnostic
screening, not a promoted full512 record.

Common identity:

- Target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- One model copy per B70 GPU
- `REALISTIC_GATE=1`
- `CANARY_REPEATS=32`
- `MAX_TOKENS=128`
- `cached_tokens=0` for every request
- `--spec-draft-n-max 3 --spec-draft-n-min 2 --spec-draft-p-min 0.0475`
- current record stack: selected-down VDR2, verifier backend argmax ids, bulk
  sampled ids, f16 KV, graph on, VMM off, `UBATCH_SIZE=1024`.

## Results

All four lanes passed the realistic validity gate:

- `fresh_response_validity.valid=true`
- `cached_tokens_all_zero=true`
- `realistic_final_gate.passed=true`
- `canary_pass_all=true`
- `canary_rows_completed=128`

| Lane | Adaptive settings | Median tok/s 1-100 after TTFT | p10 | Mean | Full after TTFT | Wall full | TTFT mean |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 control | unset | 112.020984 | 101.908880 | 112.780461 | 112.773023 | 96.584491 | 191.776 ms |
| GPU2 | warmup=4, min_full_accept=0.40 | 109.555804 | 93.111347 | 107.525014 | 105.956294 | 88.190470 | 191.997 ms |
| GPU1 | warmup=8, min_full_accept=0.50 | 103.515232 | 90.970070 | 102.723770 | 98.953220 | 84.834863 | 191.305 ms |
| GPU3 | warmup=8, min_full_accept=0.60 | 99.681293 | 90.671647 | 98.981626 | 96.603945 | 84.544589 | 192.989 ms |

Data directories:

- `data/gemma4-q8-gpu0-adaptbonus-control-strict128-20260629T200736Z/`
- `data/gemma4-q8-gpu1-adaptbonus-w8-min050-strict128-20260629T200736Z/`
- `data/gemma4-q8-gpu2-adaptbonus-w4-min040-strict128-20260629T200736Z/`
- `data/gemma4-q8-gpu3-adaptbonus-w8-min060-strict128-20260629T200736Z/`

## Interpretation

Adaptive bonus-row skipping is exact, but it loses more bonus-pipeline benefit
than it saves in verifier output rows. The best adaptive threshold lost about
`2.47 tok/s` median and had a much worse p10 than the same-build control. This
matches the earlier no-bonus and staged split-bonus findings: the bonus path is
valuable enough that row-count savings alone are not a good trade.

## Decision

Closed as a negative. No LocalMaxxing submission, no full512 promotion.

Next verifier work should avoid removing the bonus pipeline. Focus instead on a
design that preserves the bonus path while reducing work inside the existing
target decode boundary, such as compact output-row handling or MoE/head boundary
work that does not add a second graph launch.
