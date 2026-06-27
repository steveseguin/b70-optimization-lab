# 2026-06-27T05:31Z Direct-Unroll Depth Losses

## Question

Can the current direct-argmax MTP path recover enough fresh-response throughput
by blindly increasing the direct-unroll depth beyond the promoted `n=7` recipe?

The user-corrected target is **>150 tok/s fresh-response**, not merely a small
gain over the current `104.22626983476746 tok/s` record. Because current
direct-unroll acceptance is already high at `n=7`, this screen tests whether
larger draft budgets alone expose a faster regime.

## Shared Identity

All four screens used the current record stack, one full Q8 target replica on
one B70, Q4_0 MTP draft, chat benchmark mode, row0-only fresh headline,
`cached_tokens=0`, `BATCH_SIZE=1024`, `UBATCH_SIZE=768`, `MTP_N_MIN=3`,
`MTP_P_MIN=0.10`, backend draft sampling off, direct argmax IDs, fused output
argmax, qonly attention inputs, selected-softmax fused, weighted-sum, and
route-cache.

The only meaningful variable was `MTP_N_MAX` /
`LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL`.

## Results

Current promoted record for comparison:

- run dir:
  `data/gemma4-q8-gpu0-ub768-nmin3-pmin010-fullrepeat-20260627T035307Z`
- direct unroll: `7`
- canary: `6144/6144` rows pass
- cached tokens: `[0]`
- fresh row0 after TTFT: `104.22626983476746 tok/s`
- wall row0: `90.7413762430611 tok/s`
- output hash: `d4cf5f90168bd7a276a1bc3072aa2641d8b33eb7a9a269271650586091600f31`

Depth screens:

| Run | GPU | Direct Unroll | Canary | Cached Tokens | Fresh Row0 Tok/s | Wall Row0 Tok/s | Output Hash |
| --- | --- | ---: | --- | --- | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-n8-currentstack-screen-20260627T053158Z` | 0 | 8 | `64/64` | `[0]` | `66.84787263988618` | `61.05220530564796` | `d3236ebed08dda8f19a0fec78622967b3622704da06819c98a7e0e63f90d982b` |
| `data/gemma4-q8-gpu1-n9-currentstack-screen-20260627T053158Z` | 1 | 9 | `64/64` | `[0]` | `71.63228403027686` | `64.7802729295388` | `d4cf5f90168bd7a276a1bc3072aa2641d8b33eb7a9a269271650586091600f31` |
| `data/gemma4-q8-gpu2-n10-currentstack-screen-20260627T053158Z` | 2 | 10 | `64/64` | `[0]` | `76.20014071584247` | `68.55661949392798` | `d4cf5f90168bd7a276a1bc3072aa2641d8b33eb7a9a269271650586091600f31` |
| `data/gemma4-q8-gpu3-n12-currentstack-screen-20260627T053158Z` | 3 | 12 | `64/64` | `[0]` | `82.92906186353807` | `74.00134108708455` | `d4cf5f90168bd7a276a1bc3072aa2641d8b33eb7a9a269271650586091600f31` |

## Interpretation

Blindly increasing direct-unroll depth is a **valid loss** on the current
stack. Even `n=12`, the best larger-depth row, is only `82.93 tok/s`, far below
the `n=7` record and far from the `>150 tok/s` target.

This does not mean "all longer speculation is bad." It means this specific
implementation asks the scalar assistant loop to do more work without exposing
a cheaper verifier path. The current direct-unroll implementation also emits
sampled token IDs with synthetic confidence, so `MTP_P_MIN` and logit-gap
thresholds do not meaningfully prune low-value tails in this fast path.

## Decision

Status: **valid losses / stop blind depth expansion**.

Do not continue `n>7` direct-unroll sweeps unless paired with a real source
change that either:

- returns top1/top2 score or probability from the direct path so low-confidence
  tails can be cut before verifier work; or
- changes the verifier economics, for example by reducing real target MoE/LM
  head work for the small-token rows.

The next higher-upside lanes remain:

- score-aware direct unroll as a sweep enabler, not a guaranteed record path;
- small-token Gemma4 Q8 MoE verifier pipeline that preserves the tuned Q8
  matmul schedule while reducing route/materialization/launch overhead;
- exact verifier candidate-vs-max for the target LM head.
