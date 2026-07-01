# Gemma 4 26B Q8: DV512 GQA `ncols2=16` Negative

Date: 2026-07-01

Status: closed negative. Do not promote or retry without a new correctness
hypothesis.

## Goal

Test whether the existing Gemma GQA FlashAttention service lane can use a wider
DV512 GQA tile than the validated `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` path.
The motivation was prompt-processing speed only; short-context decode record
settings and quality policy are unchanged.

## Patch

Baseline/source snapshot before the experiment:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-prefill-ncols16-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-prefill-ncols16-preedit-source.diffstat`

Candidate patch:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-fattn-dv512-gqa-ncols16-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-fattn-dv512-gqa-ncols16-source.diffstat`

Candidate code added a default-off branch in
`ggml/src/ggml-sycl/fattn-tile.hpp` to allow
`GGML_SYCL_FATTN_DV512_GQA_NCOLS2=16` when `gqa_ratio <= 16`.

The candidate rebuilt successfully, but failed correctness before the long
context suite could run.

## A/B Run

Control lanes:

- GPUs: 0 and 1
- Env: `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`
- Stamp: `20260701Tncols16-ab2-control`
- Aggregate: `data/gemma4-long-context-service-gate-20260701Tncols16-ab2-control.json`

Candidate lanes:

- GPUs: 2 and 3
- Env: `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=16`
- Stamp: `20260701Tncols16-ab2-candidate`
- Aggregate: `data/gemma4-long-context-service-gate-20260701Tncols16-ab2-candidate.json`

Shared service-lane settings:

- `CTX_SIZE=32768`
- `BATCH_SIZE=2048`
- `UBATCH_SIZE=1024`
- `LLAMA_PREFILL_UBATCH_SIZE=2048`
- `FLASH_ATTN=on`
- `GGML_SYCL_ENABLE_VMM=1`
- `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`
- `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`
- Long-context cases: `lc-12288-early`, `lc-16384-late`,
  `lc-22000-middle`
- `MAX_TOKENS=96`
- `CANARY_REPEATS=2`

## Results

Control passed:

- long-context gate: pass on both lanes
- canary: pass on both lanes
- `cached_tokens=0`
- aggregate median prefill tok/s average: `1120.0763209256893`
- aggregate median decode tok/s average: `119.82548656807865`
- lane medians:
  - GPU0 prefill `1128.1856358141276`, decode `120.0141232517754`
  - GPU1 prefill `1111.9670060372512`, decode `119.63684988438189`

Candidate failed:

- both candidate lanes exited before producing `summary.json`
- aggregate rows are `missing-summary`
- both lanes failed the first JSON chat canary with empty text:
  - GPU2: `rows_completed=1`, `pass_all=false`, `text=""`,
    `normalized=""`
  - GPU3: `rows_completed=1`, `pass_all=false`, `text=""`,
    `normalized=""`

Compact evidence:

- `data/gemma4-q8-gpu2-longctx-ncols16-candidate-a-ctx32768-o96-20260701Tncols16-ab2-candidate/chat-canary.json`
- `data/gemma4-q8-gpu2-longctx-ncols16-candidate-a-ctx32768-o96-20260701Tncols16-ab2-candidate/models.json`
- `data/gemma4-q8-gpu3-longctx-ncols16-candidate-b-ctx32768-o96-20260701Tncols16-ab2-candidate/chat-canary.json`
- `data/gemma4-q8-gpu3-longctx-ncols16-candidate-b-ctx32768-o96-20260701Tncols16-ab2-candidate/models.json`

## Decision

Rejected. `ncols2=16` is not quality-safe in the current kernel path. Keep the
validated service/prefill lane on `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`.

After the failure, the active source tree was restored to the preedit record
stack by resetting the llama.cpp checkout to `c926ad098` and reapplying
`20260701-prefill-ncols16-preedit-source.patch`. The post-revert rebuild
completed successfully; `llama-server --version` reports
`version: 9769 (c926ad098)`, and the failed `forced_ncols2 == 16` branch is
absent from `ggml/src/ggml-sycl/fattn-tile.hpp`.

## Follow-Up

Do not continue by widening GQA ncols. The next prompt-processing work should
profile or improve the validated `ncols2=8` global FlashAttention path, or
target a separate short-decode verifier cost reduction. Any prompt-processing
candidate must keep the short-context decode record reproducible and must pass
the fixed realistic cold gate before promotion.
