# Gemma 4 Q8 MTP Near-Optimum Deep Sweep

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPUs 0-3 / ports 18260-18263

## Hypothesis

The first draft-MTP promotion showed that `n=4` is a valid win over no-spec,
but the n=6/n=8 smoke losses showed the tail positions are expensive. This
sweep stays near the useful region and tests whether smaller n or confidence
gating improves sustained-decode rate without changing quality.

## Run Identity

Common identity:

- model repo: `unsloth/gemma-4-26B-A4B-it-GGUF`
- main file: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft file: `mtp-gemma-4-26B-A4B-it.gguf`
- model revision: `3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a`
- runtime: llama.cpp server `dec5ca557`
- backend: SYCL / Level Zero
- context: `8192`
- batch / ubatch: `512 / 64`
- target and draft KV: `f16/f16`
- common flags: `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`,
  `POLL=50`, `REASONING=off`, `--parallel 1 --cache-ram 0`
- API mode: `/v1/chat/completions`
- canary: `CANARY_REPEATS=96` (`384` rows)
- benchmark: `BENCH_PROMPT_MODE=long`, actual `75` prompt tokens and `512`
  generated tokens, `BENCH_REPEATS=8`

## Results

| Label | GPU | MTP config | Canary | Tok/s after TTFT | Wall tok/s | CV | Acceptance | Decision |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| `gemma4-q8-gpu0-mtp-n2-long-deep2-20260623T0328` | 0 | `n=2` | 384/384 | 45.8865 | 44.3131 | 0.0209 | len `2.60`; rates `(0.858, 0.745)` | valid win over n=4, but below n=3 |
| `gemma4-q8-gpu1-mtp-n3-long-deep-20260623T0328` | 1 | `n=3` | 384/384 | **46.3562** | **44.7493** | 0.0300 | len `3.18`; rates `(0.846, 0.721, 0.610)` | **new valid best** |
| `gemma4-q8-gpu2-mtp-n5-pmin15-long-deep-20260623T0328` | 2 | `n=5`, `n_min=2`, `p_min=0.15` | 384/384 | 42.0232 | 40.7070 | 0.0203 | len `3.88`; rates `(0.847, 0.715, 0.599, 0.400, 0.321)` | loss |
| `gemma4-q8-gpu3-mtp-n6-pmin25-long-deep-20260623T0328` | 3 | `n=6`, `n_min=2`, `p_min=0.25` | 384/384 | 42.5056 | 41.1293 | 0.0587 | len `4.24`; rates `(0.852, 0.704, 0.596, 0.450, 0.330, 0.309)` | loss |

## Decision

`n=3` is the new promoted sustained-decode best: `46.356247` tok/s after TTFT,
`44.749301` wall tok/s, and `384/384` chat canary. It improves over the
approved `n=4` record (`44.499975` tok/s) by about `4.17%`, and over the
no-spec sustained-decode record (`42.716268` tok/s) by about `8.52%`.
Submitted to LocalMaxxing and approved as `cmqqbyv5w013vqo019pmp161f`.

The confidence-gated higher-n runs did not recover the speed loss. They
increased accepted length, but draft generation time rose faster than verified
output throughput. Next searches should tune around `n=3` and `n=2`, not
larger n:

- `n=3` repeat / promotion confirmation;
- `n=3` with `POLL=100`;
- `n=3` with `BATCH_SIZE=1024`;
- `n=2` with `POLL=100` or `BATCH_SIZE=1024`;
- AOT BMG build retest with `n=3` only after the non-AOT n=3 settings are
  exhausted.

## Artifacts

- summaries:
  - `data/gemma4-q8-gpu0-mtp-n2-long-deep2-20260623T0328/summary.json`
  - `data/gemma4-q8-gpu1-mtp-n3-long-deep-20260623T0328/summary.json`
  - `data/gemma4-q8-gpu2-mtp-n5-pmin15-long-deep-20260623T0328/summary.json`
  - `data/gemma4-q8-gpu3-mtp-n6-pmin25-long-deep-20260623T0328/summary.json`
- LocalMaxxing queue for the promoted n=3 result:
  - `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n3-long512-20260623.queue.json`
- LocalMaxxing response:
  - `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n3-long512-20260623.submit.log`
