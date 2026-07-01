# 2026-07-01 Final/Attention/Per-Layer Norm Fusion Combination Screen

Status: valid strict128 A/B, closed negative. Do not full512-confirm or submit.

## Question

The current promoted Gemma 4 26B Q8 record uses
`LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`. The sibling fusions
`LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL=1` and
`LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1` were already screened
individually and did not beat the headline metric. This screen tested whether
they interact positively when enabled together on top of the promoted final
post-norm recipe.

This is not a verifier-row or LM-head redesign. It was a low-risk source-flag
A/B run before deeper backend work.

## Run Identity

- date/stamp: `20260701T010630Z`
- source: `/home/steve/src/llama.cpp-gemma-record-repro-c926`, llama.cpp
  `c926ad098` dirty Gemma record stack
- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- common config: `FLASH_ATTN=on`, `CTX_SIZE=32768`,
  `GGML_SYCL_ENABLE_VMM=1`, `UBATCH_SIZE=1024`, `MAX_TOKENS=128`,
  `CANARY_REPEATS=128`, `--ctx-checkpoints 0`, Q4_0 MTP draft
  `n_max=3`, `n_min=2`, `p_min=0.0475`
- promoted flags held constant:
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`
- candidate extra flags:
  `LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL=1`,
  `LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1`

## Results

All four lanes passed the fixed realistic cold gate with `cached_tokens=0` and
the text canary.

| GPU | Lane | Result dir | Median tok/s 1-100 after TTFT | p10 |
| --- | --- | --- | ---: | ---: |
| 0 | control, final-postnorm only | `data/gemma4-q8-gpu0-normcombo-control-strict128-20260701T010630Z/summary.json` | `115.93751410280748` | `108.07923056121767` |
| 1 | final + attention + per-layer | `data/gemma4-q8-gpu1-normcombo-attnper-strict128-20260701T010630Z/summary.json` | `119.21428744324734` | `108.75993977573096` |
| 2 | control, final-postnorm only | `data/gemma4-q8-gpu2-normcombo-control-strict128-20260701T010630Z/summary.json` | `122.43093105881908` | `105.19358131458891` |
| 3 | final + attention + per-layer | `data/gemma4-q8-gpu3-normcombo-attnper-strict128-20260701T010630Z/summary.json` | `119.07574845035316` | `103.8112820382197` |

Control average: `119.18422258081328 tok/s`.

Candidate average: `119.14501794680025 tok/s`.

Current headline remains
`123.67689864739785 tok/s` from
`data/gemma4-q8-gpu0-finalpostnorm-on-full512-20260630T024027Z-finalpost-full512/summary.json`.

## Decision

Closed negative / no promotion. The combined attention + per-layer norm fusions
are valid but do not improve the current final-postnorm recipe on the primary
fresh-response metric, and the best candidate remains below the current
headline. Do not spend a full512 confirmation run on this exact combination.

Next decode work should return to the profiled bottleneck: exact verifier graph
cost, especially the backend accept-prefix verifier LM-head idea or another
profile-backed MoE boundary reduction. Avoid more generic launcher or norm
fusion sweeps without new profile evidence.
