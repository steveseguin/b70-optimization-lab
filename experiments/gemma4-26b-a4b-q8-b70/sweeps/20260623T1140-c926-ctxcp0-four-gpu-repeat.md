# Gemma 4 Q8 c926ad098 ctx-checkpoints-off four-GPU repeat

Date: 2026-06-23
Owner/agent: Codex

## Hypothesis

Repeat the new `c926ad098 --ctx-checkpoints 0` record identity across all four
B70s at once. The goal was to check whether another card/run would beat the
current validated LocalMaxxing record (`91.156717 tok/s after TTFT`) while
preserving the full 384-row chat canary.

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
- extra runtime flag: `--ctx-checkpoints 0`
- benchmark shape: `filled-long`, actual `588` prompt tokens / `512` output tokens
- gate: chat canary, `96` repeats x `4` cases = `384` rows

## Results

| Label | Gate | tok/s after TTFT | wall tok/s | TTFT ms |
| --- | ---: | ---: | ---: | ---: |
| `gemma4-q8-gpu0-mtp-n7-latest-c926ad098-ctxcp0-repeat-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T114013Z` | 384/384 | 89.863391 | 70.122297 | 1603.78 |
| `gemma4-q8-gpu1-mtp-n7-latest-c926ad098-ctxcp0-repeat-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T114013Z` | 384/384 | 90.053042 | 70.312027 | 1596.24 |
| `gemma4-q8-gpu2-mtp-n7-latest-c926ad098-ctxcp0-repeat-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T114013Z` | 384/384 | 90.174489 | 70.324685 | 1602.59 |
| `gemma4-q8-gpu3-mtp-n7-latest-c926ad098-ctxcp0-repeat-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T114013Z` | 384/384 | 90.314502 | 70.450581 | 1598.30 |

## Decision

All four repeats are valid, but none beats the current submitted high-water mark
of `91.156717 tok/s after TTFT`. Do not submit these to LocalMaxxing as new
records.

This repeat strengthens the quality/stability evidence for the identity but
also shows the `91.16` result was a high-end sample. Further progress should
come from a new mechanism or a still-untested runtime/source knob, not another
identical repeat.
