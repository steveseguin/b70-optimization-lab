# Gemma4 Q8 fused-down selected-softmax precompute negative

Date: 2026-06-29

## Question

Could the previously losing `LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX=1`
lane be rescued by precomputing selected-softmax weights once per token before
the selected-down dot work?

The current fused-down-selected-softmax VDR2 kernel recomputes selected
softmax inside each `(token, row-block)` workgroup. The experiment patch added
a default-off backend flag,
`LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX_PRECOMPUTE=1`, which:

- allocates a tiny pooled F32 scratch buffer `[n_tokens, n_expert_used]`;
- calls the existing one-work-item-per-token selected-softmax kernel into that
  buffer;
- routes the selected-down kernels as if weights were already selected weights,
  not logits.

Patch snapshot:
`patches/gemma4-fused-down-selected-softmax-precompute-negative-20260629.patch`.

The active llama.cpp source hunk was reverted after the negative full512 run.
The results harness keeps pass-through/logging for the flag so archived runs
remain self-identifying.

## Fixed identity

Same strict realistic cold-response identity as the current Gemma Q8 record:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- one B70 per replica, `CTX_SIZE=32768`, `BATCH_SIZE=1024`,
  `UBATCH_SIZE=1024`, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`;
- MTP: `n_max=3`, `n_min=2`, `p_min=0.0475`, backend sampling off,
  `--ctx-checkpoints 0`;
- record source flags including `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`,
  `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`,
  `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`,
  `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`,
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`,
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`,
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2=1`,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`.

All rows below are fixed realistic prompt suite runs, each prompt once,
`cached_tokens=0` for every request, with canary passing.

## Strict128 screen

| Lane | Primary median 1-100 tok/s | p10 | Full-output tok/s | Result |
| --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-softmaxpre-control-strict128-20260629T2329/summary.json` | 113.90838179054438 | 108.2656458113473 | 114.58886383176988 | control |
| `data/gemma4-q8-gpu1-softmaxpre-control2-strict128-20260629T2329/summary.json` | 115.27037213850834 | 105.03098440107026 | 113.37753963167987 | control |
| `data/gemma4-q8-gpu2-softmaxpre-on-strict128-20260629T2329/summary.json` | 116.66248644911582 | 103.27304984850207 | 116.562048876507 | candidate valid, not decisive |
| `data/gemma4-q8-gpu3-softmaxpre-on2-strict128-20260629T2329/summary.json` | 121.35676816201138 | 109.49729185981235 | 118.87691331258294 | candidate valid, promising but GPU3/noise-sensitive |

Strict128 justified a full512 check but was not enough to promote.

## Full512 confirmation

| Lane | Primary median 1-100 tok/s | p10 | Full512 after-TTFT tok/s | Wall full512 tok/s | TTFT ms | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-softmaxpre-control-full512-20260629T2333/summary.json` | 119.83691077465154 | 107.6733128083317 | 108.95578177163209 | 104.85270607975389 | 179.53205201774836 | control |
| `data/gemma4-q8-gpu1-softmaxpre-control2-full512-20260629T2333/summary.json` | 121.35664372753011 | 101.66979141413886 | 111.33774189285842 | 107.16434015830771 | 179.0378944715485 | control |
| `data/gemma4-q8-gpu2-softmaxpre-on-full512-20260629T2333/summary.json` | 114.99472751325114 | 108.21633321375712 | 111.57368776415971 | 106.42453439950069 | 179.76358096348122 | candidate loss |
| `data/gemma4-q8-gpu3-softmaxpre-on2-full512-20260629T2333/summary.json` | 119.55472070939985 | 105.03007180080445 | 107.8103355186012 | 103.4218440281688 | 179.10491046495736 | candidate loss |

Current valid record remains
`data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json`
at `121.41411987308553` median tok/s.

## Decision

Reject and do not submit. The precompute idea is correctness-safe under the
strict gate, but it does not beat same-build controls or the current valid
record. The added scratch kernel likely costs more than the repeated small
softmax it removes for this shape.

Carryover: if the fused-down-selected-softmax path is revisited, do it only
with a deeper kernel rewrite that keeps the precomputed weights inside the same
kernel/block or otherwise removes a larger boundary. A standalone precompute
kernel is not enough.
