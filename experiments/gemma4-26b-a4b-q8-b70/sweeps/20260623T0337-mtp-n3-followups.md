# Gemma 4 Q8 MTP n=3 Follow-Ups

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPUs 0-3 / ports 18260-18263

## Hypothesis

`n=3` became the best valid draft-MTP setting in the previous deep sweep. This
round checks whether the result reproduces and whether simple runtime knobs
(`POLL=100`, `BATCH_SIZE=1024`) or an `n=2` poll variant can improve it.

## Common Identity

- model repo: `unsloth/gemma-4-26B-A4B-it-GGUF`
- main file: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft file: `mtp-gemma-4-26B-A4B-it.gguf`
- model revision: `3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a`
- runtime: llama.cpp server `dec5ca557`
- backend: SYCL / Level Zero
- target and draft KV: `f16/f16`
- context: `8192`
- API mode: `/v1/chat/completions`
- canary: `96` repeats x `4` cases = `384` rows
- benchmark: `BENCH_PROMPT_MODE=long`, actual `75` prompt tokens and `512`
  generated tokens, `8` repeats

## Results

| Label | GPU | Config delta | Canary | Tok/s after TTFT | Wall tok/s | CV | Acceptance | Decision |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| `gemma4-q8-gpu0-mtp-n3-repeat-long-deep-20260623T0337` | 0 | repeat `n=3`, `POLL=50`, `BATCH=512` | 384/384 | **47.6301** | **45.9346** | 0.0313 | len `3.23`; rates `(0.857, 0.740, 0.636)` | **new valid best** |
| `gemma4-q8-gpu1-mtp-n3-poll100-long-deep-20260623T0337` | 1 | `n=3`, `POLL=100` | 384/384 | 46.6433 | 44.9962 | 0.0276 | len `3.21`; rates `(0.855, 0.734, 0.620)` | valid, slower |
| `gemma4-q8-gpu2-mtp-n3-b1024-long-deep-20260623T0337` | 2 | `n=3`, `BATCH=1024` | 384/384 | 46.8232 | 45.1697 | 0.0301 | len `3.19`; rates `(0.847, 0.724, 0.624)` | valid, slower |
| `gemma4-q8-gpu3-mtp-n2-poll100-long-deep-20260623T0337` | 3 | `n=2`, `POLL=100` | 384/384 | 46.1341 | 44.5388 | 0.0276 | len `2.60`; rates `(0.852, 0.750)` | valid, slower |

## Decision

The base `n=3`, `POLL=50`, `BATCH=512`, `UBATCH=64` configuration reproduced
and improved the previous record: `47.630060` tok/s after TTFT, `45.934568`
wall tok/s, with `384/384` canary. This is about `2.75%` over the previous
approved n=3 record (`46.356247`) and about `11.50%` over the no-spec
sustained-decode record (`42.716268`). Submitted to LocalMaxxing and approved
as `cmqqc99m2014cqo01s5t61bs6`.

`POLL=100`, `BATCH=1024`, and `n=2` with `POLL=100` were all valid but did not
beat the base repeat. Continue around `n=3`, but the strongest immediate
evidence is that the original base settings are still the best.

## Artifacts

- summaries:
  - `data/gemma4-q8-gpu0-mtp-n3-repeat-long-deep-20260623T0337/summary.json`
  - `data/gemma4-q8-gpu1-mtp-n3-poll100-long-deep-20260623T0337/summary.json`
  - `data/gemma4-q8-gpu2-mtp-n3-b1024-long-deep-20260623T0337/summary.json`
  - `data/gemma4-q8-gpu3-mtp-n2-poll100-long-deep-20260623T0337/summary.json`
- LocalMaxxing queue for promoted repeat:
  - `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n3-repeat-long512-20260623.queue.json`
- LocalMaxxing response:
  - `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n3-repeat-long512-20260623.submit.log`
