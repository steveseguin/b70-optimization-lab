# Filled-Long Draft-MTP Sweep

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPUs 0-3 / `18260..18263`

## Hypothesis

The earlier `long` benchmark proved draft-MTP can improve sustained decode, but
that prompt is only about 75 input tokens. The `filled-long` mode creates a
near-p512/o512 request in practice (`588` prompt tokens / `512` output tokens),
which changes cache reuse and draft acceptance behavior. The goal was to test
whether the Gemma MTP drafter becomes more valuable on the more realistic
filled prompt while preserving the 384-row chat canary gate.

## Common Identity

- model repo: `unsloth/gemma-4-26B-A4B-it-GGUF`
- main file: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- main file bytes: `27,636,230,944`
- draft file: `mtp-gemma-4-26B-A4B-it.gguf`
- draft file bytes: `461,766,816`
- runtime: llama.cpp `dec5ca557`, BMG AOT build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`
- backend: SYCL / Level Zero on one Intel Arc Pro B70
- context: `8192`
- batch / ubatch: `512 / 64`
- target and draft KV: `f16/f16`
- common flags: `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`,
  `POLL=50`, `REASONING=off`, `--parallel 1 --cache-ram 0`
- canary: `CANARY_REPEATS=96` (`384` chat rows)
- benchmark: `BENCH_PROMPT_MODE=filled-long`, actual `588` prompt tokens and
  `512` generated tokens, `BENCH_REPEATS=8`

## Results

| Label | GPU | Prompt | MTP config | Canary | Tok/s after TTFT | Wall tok/s | TTFT ms | Decision |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n3-aot-psplit005-long-deep-20260623T085322Z` | 0 | `long`, 75/512 | `n=3`, `p-split=0.05` | 384/384 | 47.4332 | 45.7456 | 397.7 | valid, below prior short-prompt record |
| `gemma4-q8-gpu1-mtp-n3-aot-psplit020-long-deep-20260623T085322Z` | 1 | `long`, 75/512 | `n=3`, `p-split=0.20` | 384/384 | 46.7650 | 45.1110 | 401.4 | loss |
| `gemma4-q8-gpu2-mtp-n3-aot-nmin2-pmin005-long-deep-20260623T085322Z` | 2 | `long`, 75/512 | `n=3`, `n-min=2`, `p-min=0.05` | 384/384 | 46.8935 | 45.2616 | 393.8 | loss |
| `gemma4-q8-gpu3-mtp-n3-aot-filled-long-deep-20260623T085322Z` | 3 | `filled-long`, 588/512 | `n=3` | 384/384 | **68.1917** | **63.4281** | 602.8 | **new filled-long record** |
| `gemma4-q8-gpu0-mtp-n2-aot-filled-long-deep-20260623T085844Z` | 0 | `filled-long`, 588/512 | `n=2` | 384/384 | 60.6861 | 56.8719 | 602.4 | valid, slower |
| `gemma4-q8-gpu1-mtp-n3-aot-psplit005-filled-long-deep-20260623T085844Z` | 1 | `filled-long`, 588/512 | `n=3`, `p-split=0.05` | 384/384 | 68.2219 | 63.4269 | 604.2 | tiny valid edge, below later record |
| `gemma4-q8-gpu2-mtp-n3-aot-psplit020-filled-long-deep-20260623T085844Z` | 2 | `filled-long`, 588/512 | `n=3`, `p-split=0.20` | 384/384 | **68.5147** | **63.6664** | 610.8 | **new record at the time** |
| `gemma4-q8-gpu3-mtp-n4-aot-filled-long-deep-20260623T085822Z` | 3 | `filled-long`, 588/512 | `n=4` | 384/384 | **74.3947** | **68.7973** | 601.5 | **current best** |

## Decision

The filled-long shape changed the optimum. Short-prompt `long` remained best at
AOT `n=3`, but filled-long strongly favored `n=4`, which reached
`74.394656` tok/s after TTFT with a 384/384 canary pass. This is the current
valid best for the Gemma 4 26B A4B Q8 one-B70 lane and was approved by
LocalMaxxing as `cmqqf75p70157qo018fsavf0g`.

The `p-split=0.20` filled-long variant was also valid and briefly improved the
record to `68.514684` tok/s after TTFT; it was submitted and approved as
`cmqqf759s0154qo01gwqa14uc`. The earlier filled-long `n=3` base was approved as
`cmqqexo5x0151qo0154xsie7s`.

`n=2` is too conservative for filled-long. `p-split=0.05` and `p-split=0.20`
do not close the gap to `n=4`. The next useful sweep should stay on
filled-long and test deeper draft budgets (`n=5`, gated `n=6`) and `n=4`
launcher/runtime variants rather than returning to short-prompt `long` tuning.

## Artifacts

- summaries:
  - `data/gemma4-q8-gpu0-mtp-n3-aot-psplit005-long-deep-20260623T085322Z/summary.json`
  - `data/gemma4-q8-gpu1-mtp-n3-aot-psplit020-long-deep-20260623T085322Z/summary.json`
  - `data/gemma4-q8-gpu2-mtp-n3-aot-nmin2-pmin005-long-deep-20260623T085322Z/summary.json`
  - `data/gemma4-q8-gpu3-mtp-n3-aot-filled-long-deep-20260623T085322Z/summary.json`
  - `data/gemma4-q8-gpu0-mtp-n2-aot-filled-long-deep-20260623T085844Z/summary.json`
  - `data/gemma4-q8-gpu1-mtp-n3-aot-psplit005-filled-long-deep-20260623T085844Z/summary.json`
  - `data/gemma4-q8-gpu2-mtp-n3-aot-psplit020-filled-long-deep-20260623T085844Z/summary.json`
  - `data/gemma4-q8-gpu3-mtp-n4-aot-filled-long-deep-20260623T085822Z/summary.json`
- LocalMaxxing queues:
  - `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n3-aot-filledlong512-20260623.queue.json`
  - `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n3-aot-psplit020-filledlong512-20260623.queue.json`
  - `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n4-aot-filledlong512-20260623.queue.json`
- LocalMaxxing responses:
  - `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n3-aot-filledlong512-20260623.submit.log`
  - `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n3-aot-psplit020-filledlong512-20260623.submit.log`
  - `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n4-aot-filledlong512-20260623.submit.log`
