# Filled-Long `n=4` Follow-Ups

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPUs 0-3 / `18260..18263`

## Hypothesis

The filled-long sweep made draft-MTP `n=4` the current best at
`74.394656` tok/s after TTFT. This follow-up tested low-risk knobs around that
winner: confidence thresholding, p-split, continuous batching, and host/draft
batch polling.

## Common Identity

- model repo: `unsloth/gemma-4-26B-A4B-it-GGUF`
- main file: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft file: `mtp-gemma-4-26B-A4B-it.gguf`
- runtime: llama.cpp `dec5ca557`, BMG AOT build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`
- backend: SYCL / Level Zero on one Intel Arc Pro B70
- context: `8192`
- target and draft KV: `f16/f16`
- common flags: `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`,
  `POLL=50`, `THREADS=16`, `REASONING=off`, `--parallel 1 --cache-ram 0`
- MTP base: `--spec-type draft-mtp --spec-draft-n-max 4`
- canary: `CANARY_REPEATS=96` (`384` chat rows)
- benchmark: `BENCH_PROMPT_MODE=filled-long`, actual `588` prompt tokens and
  `512` generated tokens, `BENCH_REPEATS=8`

## Results

| Label | GPU | Config delta | Canary | Tok/s after TTFT | Wall tok/s | TTFT ms | Decision |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n4-aot-pmin010-filled-long-deep-20260623T090712Z` | 0 | `--spec-draft-p-min 0.10` | 384/384 | 74.2996 | 68.6968 | 601.4 | valid, below record |
| `gemma4-q8-gpu1-mtp-n4-aot-psplit020-filled-long-deep-20260623T090712Z` | 1 | `--spec-draft-p-split 0.20` | 384/384 | **74.4981** | **68.8999** | 599.4 | **new record** |
| `gemma4-q8-gpu2-mtp-n4-aot-nocontbatch-filled-long-deep-20260623T090712Z` | 2 | `--no-cont-batching` | 384/384 | 74.2163 | 68.4844 | 619.1 | valid, below record |
| `gemma4-q8-gpu3-mtp-n4-aot-batchpoll-filled-long-deep-20260623T090712Z` | 3 | `--spec-draft-threads-batch 32 --threads-batch 32 --poll-batch 1 --spec-draft-poll-batch 1` | 384/384 | 74.1562 | 68.5012 | 614.7 | valid, below record |

## Decision

`--spec-draft-p-split 0.20` is a tiny but valid improvement over the previous
filled-long `n=4` record: `74.498091` tok/s after TTFT, `68.899854` wall tok/s,
and `384/384` canary. It was submitted to LocalMaxxing and approved as
`cmqqfe75s015aqo01xr94yxh0`.

The other three variants are useful negatives. `p-min=0.10` did not improve
acceptance enough to beat the record, disabling continuous batching did not
help single-session decode, and host/draft batch polling was slower. Continue
from `n=4 + p-split=0.20`, then test a repeat, a deeper `n=5` budget, a gated
`n=6` budget, and `BATCH_SIZE=1024` combined with `p-split=0.20`.

## Artifacts

- summaries:
  - `data/gemma4-q8-gpu0-mtp-n4-aot-pmin010-filled-long-deep-20260623T090712Z/summary.json`
  - `data/gemma4-q8-gpu1-mtp-n4-aot-psplit020-filled-long-deep-20260623T090712Z/summary.json`
  - `data/gemma4-q8-gpu2-mtp-n4-aot-nocontbatch-filled-long-deep-20260623T090712Z/summary.json`
  - `data/gemma4-q8-gpu3-mtp-n4-aot-batchpoll-filled-long-deep-20260623T090712Z/summary.json`
- LocalMaxxing queue:
  - `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n4-aot-psplit020-filledlong512-20260623.queue.json`
- LocalMaxxing response:
  - `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n4-aot-psplit020-filledlong512-20260623.submit.log`
