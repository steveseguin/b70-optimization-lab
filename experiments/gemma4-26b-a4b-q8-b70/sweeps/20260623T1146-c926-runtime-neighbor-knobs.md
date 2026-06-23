# Gemma 4 Q8 c926ad098 runtime neighbor knobs

Date: 2026-06-23
Owner/agent: Codex

## Hypothesis

Test cheap runtime/source-adjacent knobs around the current valid high-water
identity (`91.156717 tok/s after TTFT`, `c926ad098`, `--ctx-checkpoints 0`) to
see whether any single low-risk toggle beats the record while preserving the
full 384-row chat canary.

## Shared Run Identity

- runtime:
  `/home/steve/src/llama.cpp-latest-gemma/build-sycl-b70-aot-bmg-g31/bin/llama-server`
- llama.cpp: `c926ad098`, version `9769`
- model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/mtp-gemma-4-26B-A4B-it.gguf`
- one full model replica per B70 via `ONEAPI_DEVICE_SELECTOR=level_zero:<gpu>`
- MTP: `n-max=7`, `n-min=2`, `p-min=0.12`, backend sampling off
- draft threads / draft batch threads: `32 / 32`
- base extra runtime flag: `--ctx-checkpoints 0`
- benchmark shape: `filled-long`, actual `588` prompt tokens / `512` output tokens
- gate: chat canary, `96` repeats x `4` cases = `384` rows

Two first attempts (`draftpoll0` and `syclvmm0`) had invalid shell syntax in the
parallel launcher and produced only `/tmp` launcher-error files. They were not
benchmark results and are not tracked. Corrected runs are labeled `fixed`.

## Results

| Label | Delta | Gate | tok/s after TTFT | wall tok/s | TTFT ms | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-latest-c926ad098-ctxcp0-draftpoll0-fixed-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T114717Z` | `--spec-draft-poll 0` | 384/384 | 90.044504 | 70.252148 | 1602.04 | Valid, not a record. |
| `gemma4-q8-gpu1-mtp-n7-latest-c926ad098-ctxcp0-syclvmm0-fixed-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T114717Z` | `GGML_SYCL_ENABLE_VMM=0` | 384/384 | 90.273064 | 70.219924 | 1619.80 | Valid, not a record. |
| `gemma4-q8-gpu2-mtp-n7-latest-c926ad098-ctxcp0-nokvunified-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T114636Z` | `--no-kv-unified` | 384/384 | 90.534641 | 70.635701 | 1593.22 | Best of batch, still not a record. |
| `gemma4-q8-gpu3-mtp-n7-latest-c926ad098-ctxcp0-samplersgreedy-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T114636Z` | `--samplers greedy` | 384/384 | 89.186187 | 69.773447 | 1597.29 | Valid loss. |

## Decision

Do not submit any of these to LocalMaxxing. All four corrected candidates pass
quality, but none beats the current record. The best candidate,
`--no-kv-unified`, landed at `90.534641 tok/s`, below both the `91.156717`
record and the previous `dec5ca557` `91.045654` record.

These knobs are now treated as exhausted for the current `c926ad098
--ctx-checkpoints 0` identity unless paired with a genuinely new mechanism.
Further optimization should focus on the MTP implementation path, especially the
target `h_nextn` hidden-state handoff and draft-generation overhead.
