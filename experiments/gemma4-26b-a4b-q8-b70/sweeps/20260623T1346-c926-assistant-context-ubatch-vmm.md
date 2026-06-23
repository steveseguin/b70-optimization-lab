# c926 assistant, context, ubatch, and VMM sweep

Date: 2026-06-23
Owner/agent: Codex
GPU / ports: GPUs 0-3, ports 18470-18473

## Hypothesis

After the raw-prob draft top-k patch proved too expensive, this sweep returned
to no-source-change experiments under the current best `c926ad098` identity.
The goals were:

- test alternate Gemma 4 MTP draft files now that upstream llama.cpp has
  `gemma4-assistant` support;
- test whether smaller context or larger ubatch improves the `588/512`
  filled-long shape;
- combine prior near-misses (`GGML_SYCL_ENABLE_VMM=0`, `--no-kv-unified`) with
  larger ubatches;
- verify whether higher-precision F16/BF16 MTP heads improve acceptance enough
  to pay for their size.

## Run Identity

Unless noted otherwise:

- target model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- target bytes: `27,636,230,944`
- default draft: `mtp-gemma-4-26B-A4B-it.gguf`
- runtime: llama.cpp SYCL AOT BMG build
- runtime commit/version: `c926ad098`, version `9769`
- backend: Intel oneAPI Level Zero / SYCL, one B70 per replica
- default context: `8192`
- default batch / ubatch: `512 / 64`
- KV cache dtype: f16/f16, draft f16/f16
- API mode: OpenAI-compatible `llama-server`, `--parallel 1 --cache-ram 0`
- prompt: `BENCH_PROMPT_MODE=filled-long`, usage-derived `588` prompt / `512`
  completion tokens
- validation: `CANARY_REPEATS=96` over four chat-canary cases (`384/384`)
- benchmark: `BENCH_REPEATS=8`
- base MTP flags: `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`,
  `MTP_BACKEND_SAMPLING=0`, `MTP_DRAFT_THREADS=32`,
  `MTP_DRAFT_THREADS_BATCH=32`, `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`

Current valid record for comparison:

- `gemma4-q8-gpu0-mtp-n7-latest-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T113058Z`
- `91.15671739968305 tok/s` after TTFT, `384/384` canary

## Result

All benchmarked lanes preserved the `384/384` canary gate but failed to beat the
record. The AtomicChat assistant file failed at model load and was not a
benchmark result.

| Label | Gate | after-TTFT tok/s | wall tok/s | TTFT s | best repeat tok/s | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-c926-control-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T134602Z` | 384/384 | 89.879310 | 70.212931 | 1.595620 | 90.417608 | valid loss |
| `gemma4-q8-gpu3-mainq80-mtp-n7-c926-unslothassistant-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T134602Z` | 384/384 | 89.077566 | 69.447829 | 1.624656 | 89.305404 | valid Q8_0 main loss |
| `gemma4-q8-gpu1-mtp-n7-c926-atomicassistantq80-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T134602Z` | load fail | - | - | - | - | AtomicChat metadata incompatible: `gemma4_assistant` |
| `gemma4-q8-gpu2-mtp-n8-c926-atomicassistantq80-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T134602Z` | load fail | - | - | - | - | AtomicChat metadata incompatible: `gemma4_assistant` |
| `gemma4-q8-gpu1-mtp-n8-c926-unslothassistant-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T134602Zb` | 384/384 | 61.798650 | 51.822595 | 1.594939 | 61.844789 | n=8 still rejected |
| `gemma4-q8-gpu2-mtp-n7-c926-unslothassistant-ctxcp0-nmin2-pmin0115-nobs-dthreads32-dtb32-filled-long-deep-20260623T134602Zb` | 384/384 | 89.957037 | 70.231978 | 1.598720 | 90.542754 | valid loss |
| `gemma4-q8-gpu0-mtp-n7-c926-ctx4096-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1410Z` | 384/384 | 90.107887 | 70.301731 | 1.600875 | 90.329367 | valid loss |
| `gemma4-q8-gpu3-mtp-n7-c926-ub128-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1410Z` | 384/384 | 89.929711 | 76.592991 | 0.991535 | 90.153357 | valid loss; wall improves |
| `gemma4-q8-gpu1-mtp-n7-c926-unsloth-mtpq80file-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1415Z` | 384/384 | 90.329857 | 70.433591 | 1.601124 | 92.136613 | valid official MTP Q8_0 loss |
| `gemma4-q8-gpu2-mtp-n7-c926-ub256-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1415Z` | 384/384 | 90.345667 | 79.732432 | 0.756157 | 91.140930 | valid loss; wall improves |
| `gemma4-q8-gpu0-mtp-n7-c926-ctx2048-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1420Z` | 384/384 | 90.096605 | 70.400552 | 1.589905 | 90.342089 | valid loss |
| `gemma4-q8-gpu3-mtp-n7-c926-b256ub64-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1420Z` | 384/384 | 90.113335 | 70.371775 | 1.593962 | 90.202018 | valid loss |
| `gemma4-q8-gpu1-mtp-n7-c926-ctx4096ub256-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1428Z` | 384/384 | 90.064356 | 79.538436 | 0.753855 | 90.312891 | valid loss |
| `gemma4-q8-gpu2-mtp-n7-c926-ub512-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1428Z` | 384/384 | 90.084652 | 81.040238 | 0.637622 | 91.354467 | valid loss; best wall-only lane so far |
| `gemma4-q8-gpu0-mtp-n7-c926-f16mtp-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1436Z` | 384/384 | 86.161458 | 67.861499 | 1.602556 | 87.004368 | F16 draft loss |
| `gemma4-q8-gpu1-mtp-n7-c926-nokvunified-ub512-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1436Z` | 384/384 | 90.084270 | 80.962923 | 0.642289 | 91.895942 | valid loss |
| `gemma4-q8-gpu2-mtp-n7-c926-vmm0-ub512-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1436Z` | 384/384 | 90.772263 | 81.658553 | 0.631818 | 92.058491 | closest mean of wave, still below record |
| `gemma4-q8-gpu3-mtp-n7-c926-ctx4096ub512-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1436Z` | 384/384 | 90.136402 | 81.141489 | 0.631891 | 90.373057 | valid loss |
| `gemma4-q8-gpu0-mtp-n7-c926-vmm0-ub512-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1448Z` | 384/384 | 90.215581 | 81.187121 | 0.632932 | 91.794703 | repeat did not confirm 90.77 |
| `gemma4-q8-gpu1-mtp-n7-c926-vmm0-ctx4096ub512-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1448Z` | 384/384 | 90.391344 | 81.258900 | 0.638673 | 91.257796 | valid loss |
| `gemma4-q8-gpu2-mtp-n7-c926-vmm0-ub512-pmin0115-ctxcp0-nmin2-nobs-dthreads32-dtb32-filled-long-deep-20260623T1448Z` | 384/384 | 90.506827 | 81.434657 | 0.632263 | 91.969659 | valid loss |
| `gemma4-q8-gpu3-mtp-n7-c926-bf16mtp-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1448Z` | 384/384 | 86.139317 | 77.883298 | 0.632051 | 87.605889 | BF16 draft loss |

## Decisions

- No LocalMaxxing submission: no lane beat the promoted `91.156717 tok/s`
  after-TTFT record with full canary validation.
- The stock upstream-compatible draft remains the root Unsloth
  `mtp-gemma-4-26B-A4B-it.gguf` / official `MTP/...Q8_0-MTP.gguf` family. The
  AtomicChat assistant GGUF is a fork-format artifact (`gemma4_assistant`,
  `mtp.*`) and should be reserved for AtomicChat's custom `--mtp-head` fork or a
  deliberate conversion-on-copy experiment.
- Higher-precision draft heads do not help this B70 lane. F16 and BF16 both
  preserve quality but drop decode to about `86.1 tok/s`.
- Larger ubatches improve TTFT and wall throughput materially (`~81 tok/s wall`
  versus the promoted c926 lane's `71 tok/s wall`), but the promoted after-TTFT
  decode metric remains below record. Keep `ub512` as a wall-latency side lane,
  not the sustained-decode record path.
- `GGML_SYCL_ENABLE_VMM=0 + ub512` is the closest interaction in this wave, but
  the repeat landed at only `90.22 tok/s`; do not promote.

## Follow-up

The no-patch c926 search around model identity, context, ubatch, VMM, and draft
precision appears exhausted for the current record metric. The next meaningful
speed attempt is source-level and should be treated as a patch experiment:

- expose a cheap draft top-k / top-1 confidence path without full raw-softmax
  rescale, gated behind env vars and full `384/384` validation; or
- profile and reduce draft-MTP candidate selection overhead directly.

Do not repeat high-depth `n=8/n=9`, p-split `0.05-0.20`, rawprob top-k, Q8_0
main, F16/BF16 draft heads, or AtomicChat assistant-on-stock-llama.cpp unless a
runtime/source change invalidates the current evidence.

## Artifacts

Structured run directories are under `data/<label>/`. Full server logs are under
`/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/<label>.server.log`.
Downloaded MTP draft file metadata is stored next to the local GGUFs:

- `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q8_0-MTP.gguf.metadata.json`
- `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-F16-MTP.gguf.metadata.json`
- `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-BF16-MTP.gguf.metadata.json`
