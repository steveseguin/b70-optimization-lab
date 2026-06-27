# Gemma 4 26B Q8 MoE-ID Q8_0 Reorder Patch Snapshot

Date: 2026-06-27

Status: **promising positive**, pending full 6144-row canary confirmation at
time of this snapshot.

This records the focused patch behind the `~170 tok/s` Gemma 4 26B Q8 screens.
The llama.cpp source worktree contains many older Gemma experiments, so do not
archive the whole dirty `git diff` as this patch. The material delta is the
Q8_0 MoE expert-weight reorder support for the broad multi-token
`MUL_MAT_ID` verifier path.

## Source Locations

Source tree:
`/home/steve/src/llama.cpp-gemma-record-repro-c926`

Focused source files:

- `ggml/src/ggml-sycl/ggml-sycl.cpp`
- `ggml/src/ggml-sycl/mmvq.cpp`
- `ggml/src/ggml-sycl/mmvq.hpp`

Harness files:

- `/home/steve/qwen36-results-main/scripts/run-gemma4-26b-first-baseline.sh`
- `/home/steve/qwen36-results-main/scripts/run-gemma4-26b-llamacpp-replica.sh`

## Patch Shape

The patch adds a default-off opt-in:

```bash
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1
```

When enabled, Q8_0 MoE expert slices are lazily reordered once into a
self-contained `[qs][d]` layout per expert and then routed through the existing
multi-token reorder MMVQ body.

Important implementation points:

- `reorder_qw_q8_0_moe(uint8_t * data_device, size_t expert_bytes,
  int64_t n_expert, dpct::queue_ptr stream)` reorders each expert slice using
  `expert_bytes`, not the whole tensor as one continuous matrix.
- The MoE branch of `reorder_qw(...)` dispatches `GGML_TYPE_Q8_0` to that new
  per-expert reorder.
- `opt_for_reorder_id(...)` allows Q8_0 reorder only when
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`.
- `ggml_sycl_mul_mat_id_multi_token_direct_supports(..., use_reorder=true)`
  now includes `GGML_TYPE_Q8_0`.
- `ggml_sycl_mul_mat_vec_q_id_multi_token_reorder(...)` includes a Q8_0 case
  using `reorder_vec_dot_q_sycl<GGML_TYPE_Q8_0>`.
- The run harness forwards and records
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER` in launcher identity.

## Why It Matters

Before this patch, broad
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1` on the Q8 target was a severe
regression because the fast multi-token MoE-ID path could not use a reorder
layout for Q8_0 expert weights. With this opt-in, the same broad path becomes
the first real path above the project target of `>150 tok/s` fresh-response
throughput.

## A/B Evidence

Candidate:

- run:
  `data/gemma4-q8-gpu1-mulmatid-fast-q8reorder-ub768-screen-20260627T142028Z/`
- canary: `256/256`
- fresh row0 after TTFT: `170.07964702612907 tok/s`
- support mean: `170.09471150714091 tok/s`
- cached tokens: `[0, 0, 0]`
- flags: `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`,
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`, `UBATCH_SIZE=768`,
  `MTP_N_MAX=7`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`

Control:

- run:
  `data/gemma4-q8-gpu2-mulmatid-fast-control-ub768-screen-20260627T142028Z/`
- canary: `256/256`
- fresh row0 after TTFT: `77.31483253873125 tok/s`
- support mean: `77.33554453239168 tok/s`
- same broad fast path, but without `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`

Interpretation: the Q8_0 reorder is the enabling change. The broad
multi-token MoE-ID fast path remains a regression without it.

## Current Best Screens

- `UBATCH_SIZE=704`, `n_min=3`, `p_min=0.10`:
  `171.13964433413412 tok/s` row0, `256/256` canary, screen only.
- `UBATCH_SIZE=768`, `n_min=3`, `p_min=0.10`:
  `170.07964702612907 tok/s` row0, `256/256` canary, screen only.
- `UBATCH_SIZE=832`, `n_min=3`, `p_min=0.10`:
  `169.1340657718682 tok/s` row0, `256/256` canary, screen only.

Known slower variants:

- `n_max=8` collapsed to about `89 tok/s`.
- `n_max=6` was valid but slower at about `160 tok/s`.
- `p_min=0.08` and `p_min=0.12` were slower than `0.10` in screens.

## Promotion Gate

Do not submit or headline this patch from screens alone. A promoted record
requires:

- `canary_pass_all == true`;
- `canary_rows_completed == 6144` for the 1536-repeat four-case gate;
- `fresh_response_validity.headline_cached_tokens == 0`;
- benchmark row 0 reports `usage.prompt_tokens_details.cached_tokens == 0`;
- headline throughput uses row 0 only. Later repeated-prompt rows are
  support-only.

Full confirmations launched:

- `data/gemma4-q8-gpu0-mulmatid-fast-q8reorder-ub768-fullconfirm-20260627T142318Z/`
- `data/gemma4-q8-gpu1-q8reorder-ub704-nmin3-pmin010-fullconfirm-20260627T143126Z/`
