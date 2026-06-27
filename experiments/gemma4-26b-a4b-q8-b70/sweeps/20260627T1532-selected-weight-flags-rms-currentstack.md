# 2026-06-27T15:32Z Selected-Weight Flags With Current RMS Identity

## Goal

Retest the selected-weight materialization flags after correcting the
`20260627T1528` benchmark-identity mistake. These runs include the promoted
UB720 stack's `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1` flag.

Headline policy: row0 only, `cached_tokens=0`; repeated benchmark rows are
support-only.

## Run Identity

Common identity:

- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- one B70 GPU per run, `--parallel 1`, `--cache-ram 0`
- `--spec-type draft-mtp`, `n_max=7`, `n_min=3`, `p_min=0.10`
- `CTX_SIZE=8192`, `BATCH_SIZE=1024`, `UBATCH_SIZE=720`
- `PROMPT_TOKENS=512`, `MAX_TOKENS=512`, `BENCH_PROMPT_MODE=filled-long`
- Q8 reorder lane:
  - `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`
  - `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`
  - `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`

## Results

| Run | Canary | Fresh row0 tok/s | Support mean tok/s | Cached tokens | Status |
| --- | ---: | ---: | ---: | --- | --- |
| `data/gemma4-q8-gpu0-q8reorder-ub720-rms-control-20260627T153259Z/` | 256/256 | 169.391 | 168.990 | `[0,0,0]` | Simultaneous control |
| `data/gemma4-q8-gpu1-q8reorder-ub720-rms-skipearly-20260627T153259Z/` | 256/256 | 170.522 | 170.076 | `[0,0,0]` | Small positive screen vs simultaneous control, below promoted 171.108 |
| `data/gemma4-q8-gpu2-q8reorder-ub720-rms-ssws-20260627T153259Z/` | 256/256 | 169.222 | 169.127 | `[0,0,0]` | Loss |
| `data/gemma4-q8-gpu3-q8reorder-ub720-rms-ssws-skipearly-20260627T153259Z/` | 256/256 | 167.605 | 167.623 | `[0,0,0]` | Loss |

## Decision

`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM=1` is rejected on the current
stack. Combining it with `LLAMA_GEMMA4_MOE_SKIP_EARLY_WEIGHTS_EXPAND=1` is also
rejected.

`LLAMA_GEMMA4_MOE_SKIP_EARLY_WEIGHTS_EXPAND=1` deserves one solo GPU0 screen
because it was the only positive simultaneous result, but it is not promoted
unless row0 beats the current full-confirmed record
`171.1076295077342 tok/s` and then passes full confirmation.

## Solo Follow-Up

| Run | Canary | Fresh row0 tok/s | Support mean tok/s | Cached tokens | Decision |
| --- | ---: | ---: | ---: | --- | --- |
| `data/gemma4-q8-gpu0-q8reorder-ub720-rms-skipearly-solo-20260627T153536Z/` | 256/256 | 170.448 | 170.676 | `[0,0,0]` | Valid loss versus promoted `171.108` |

Final decision: reject `LLAMA_GEMMA4_MOE_SKIP_EARLY_WEIGHTS_EXPAND=1` for the
promoted recipe. It is correctness-clean and roughly neutral-to-small-positive
in some screens, but it did not beat the current record when rerun alone on
GPU0. Do not spend a full confirmation on this flag unless another source
change makes it newly relevant.
