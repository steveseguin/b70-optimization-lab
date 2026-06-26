# Runtime Frontier Recheck: Threads, Batch, And p-min

Date: 2026-06-26
Owner/agent: Codex

## Hypothesis

The current Gemma 4 26B A4B Q8 fresh-response record sits close to the local
runtime frontier. Before changing source again, recheck small runtime
perturbations that could plausibly win through thread scheduling, larger
capture/batch shape, or a slightly lower MTP p-min threshold.

## Shared Identity

- target model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- target/verifier quality lane: Q8 target, Q4_0 MTP draft only
- runtime: llama.cpp `c926ad098`, local dirty Gemma record stack
- shape: filled-long, actual `588` prompt tokens / `512` output tokens
- validation: chat canary `384/384` for every lane
- freshness: row0 only, `cached_tokens=0` for every lane
- common env:
  `MTP_N_MAX=7`, `MTP_N_MIN=2`, backend draft sampling off,
  `MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=32`,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`,
  `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`,
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`,
  `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`,
  `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`,
  `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`,
  `GGML_SYCL_ENABLE_VMM=0`, `GGML_SYCL_DISABLE_GRAPH=0`,
  `FLASH_ATTN=off`, `POLL=100`, `--ctx-checkpoints 0`

Current record to beat:

- `data/gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-20260625T031510Z/summary.json`
- fresh row0: `103.2992004295621 tok/s` after TTFT
- support mean: `102.19335537277364 tok/s`
- LocalMaxxing: `cmqsylo2l011nqr011yydjvne`

## Results

| Label | GPU | Delta | Fresh row0 tok/s | Wall tok/s | TTFT s | Canary | Decision |
|---|---:|---|---:|---:|---:|---:|---|
| `gemma4-q8-gpu0-control-pmin0136-screen-20260626T071759Z` | 0 | exact record-family control, `THREADS=8`, `BATCH=1024`, `UBATCH=1024`, `pmin=0.136` | `102.32420312079226` | `88.72667100985785` | `0.7668271759757772` | `384/384` | valid loss |
| `gemma4-q8-gpu1-th16-pmin0136-screen-20260626T071759Z` | 1 | `THREADS=16` | `102.3382408163026` | `88.6508173649619` | `0.7724510590196587` | `384/384` | valid loss |
| `gemma4-q8-gpu2-th16-bu1152-pmin0136-screen-20260626T071759Z` | 2 | `THREADS=16`, `BATCH=1152`, `UBATCH=1152` | `102.32356266126699` | `88.75669205225805` | `0.7648440339835361` | `384/384` | valid loss |
| `gemma4-q8-gpu3-pmin01355-screen-20260626T071759Z` | 3 | `pmin=0.1355` | `100.36453524411831` | `87.28278690164501` | `0.7645869280095212` | `384/384` | valid loss |

## Decision

No new LocalMaxxing submission. None beat the `103.2992004295621 tok/s` fresh
row0 record. The `THREADS=16` and `BATCH/UBATCH=1152` variants are effectively
neutral-to-slightly-slower; `pmin=0.1355` is clearly worse in this repeat. Keep
the promoted runtime recipe at `THREADS=8`, `BATCH_SIZE=1024`,
`UBATCH_SIZE=1024`, and `MTP_P_MIN=0.136`.

This reinforces the profile conclusion from
`data/gemma4-q8-gpu0-record-profile-20260626T0810/summary.json`: the remaining
frontier is the target verifier/model compute (`process_ubatch`), not draft
acceptance, p-min thresholding, sampler extraction, or small thread/batch
runtime knobs.

## Artifacts

- `data/gemma4-q8-gpu0-control-pmin0136-screen-20260626T071759Z/summary.json`
- `data/gemma4-q8-gpu1-th16-pmin0136-screen-20260626T071759Z/summary.json`
- `data/gemma4-q8-gpu2-th16-bu1152-pmin0136-screen-20260626T071759Z/summary.json`
- `data/gemma4-q8-gpu3-pmin01355-screen-20260626T071759Z/summary.json`
- runner output logs:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/runtime-screens/*20260626T071759Z.out`
