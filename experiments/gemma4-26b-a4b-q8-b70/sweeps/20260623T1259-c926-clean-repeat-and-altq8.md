# Gemma 4 Q8 c926 clean repeat and alternate Q8 screen

Date: 2026-06-23
Owner/agent: Codex

## Hypothesis

After reverting the diagnostic MTP timing patch, rebuild the clean
`c926ad098` llama.cpp binary and re-anchor the current record family. Also test
two nearby `p-min` values and the alternate `Q8_0` main GGUF under the same
current MTP identity.

The web/source audit suggested `Q8_0` can be a plausible SYCL speed candidate
because recent llama.cpp SYCL notes call out `Q8_0`-family optimized paths more
explicitly than Unsloth `UD-*` formats. The prior `dec5ca557` Q8_0 control lost,
but it had not yet been repeated on the clean latest runtime.

## Shared Identity

- runtime: clean `/home/steve/src/llama.cpp-latest-gemma`, llama.cpp
  `c926ad098`, version `9769`, rebuilt after the timing patch was reverted;
- server binary:
  `/home/steve/src/llama.cpp-latest-gemma/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- default main model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- alternate main model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-Q8_0.gguf`;
- draft model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/mtp-gemma-4-26B-A4B-it.gguf`;
- one full model replica per B70 via `ONEAPI_DEVICE_SELECTOR=level_zero:<gpu>`;
- common MTP: `n-max=7`, `n-min=2`, backend sampling off, draft threads `32`,
  draft batch threads `32`, draft KV `f16/f16`;
- common extra args: `--parallel 1 --cache-ram 0 --ctx-checkpoints 0`;
- shape: `BENCH_PROMPT_MODE=filled-long`, `588` prompt tokens / `512`
  completion tokens;
- gate: chat canary `96` repeats x `4` cases = `384/384`.

## Results

| Variant | Main model | Gate | tok/s after TTFT | wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `repeat-clean` | `UD-Q8_K_XL` | 384/384 | 90.872394 | 70.863961 | 1.590926 | Valid repeat, below record |
| `pmin0125` | `UD-Q8_K_XL` | 384/384 | 90.079274 | 70.291129 | 1.600164 | Loss |
| `pmin013` | `UD-Q8_K_XL` | 384/384 | 90.274264 | 70.404508 | 1.600715 | Loss |
| `q80-model` | `Q8_0` | 384/384 | 89.248814 | 69.510002 | 1.629115 | Valid Q8_0 loss |

Current record remains:

- `gemma4-q8-gpu0-mtp-n7-latest-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T113058Z`
- `91.156717 tok/s` after TTFT, `384/384`, LocalMaxxing
  `cmqqkmbhr017oqo017rdfxqh2`.

## Artifacts

- `data/gemma4-q8-gpu0-mtp-n7-latest-c926ad098-repeat-clean-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T125932Z/summary.json`
- `data/gemma4-q8-gpu1-mtp-n7-latest-c926ad098-pmin0125-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T125932Z/summary.json`
- `data/gemma4-q8-gpu2-mtp-n7-latest-c926ad098-pmin013-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T125932Z/summary.json`
- `data/gemma4-q8-gpu3-mtp-n7-latest-c926ad098-q80-model-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T125932Z/summary.json`

## Decision

No LocalMaxxing submission. All four variants passed quality but failed to beat
the current record. The clean repeat at `90.87 tok/s` is closer than the earlier
four-GPU c926 repeat cluster, but still below `91.1567`; the high-water mark
remains valid but difficult to reproduce. The alternate main `Q8_0` model is
not a speed replacement for `UD-Q8_K_XL` under this identity.
