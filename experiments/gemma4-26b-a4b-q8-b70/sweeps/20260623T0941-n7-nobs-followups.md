# 20260623T0941 N7 No-Backend-Sampling Follow-Ups

Goal: take the `90.243 tok/s` no-backend-sampling record and test the nearest
confidence / draft-runtime knobs without changing model quality, prompt shape,
or the 384-row chat canary gate.

Common identity:

- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, AOT BMG build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `mtp-gemma-4-26B-A4B-it.gguf`;
- flags: `BENCH_PROMPT_MODE=filled-long`, `GGML_SYCL_DISABLE_OPT=0`,
  `FLASH_ATTN=off`, `POLL=50`, `--parallel 1 --cache-ram 0`, f16 main and
  draft KV, `--no-spec-draft-backend-sampling`;
- quality gate: `384/384` chat canary before promotion;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

## Results

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin008-nobs-filled-long-deep-20260623T094131Z` | `p-min=0.08` | 384/384 | 89.974 | 82.024 | Valid, below record. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin012-nobs-filled-long-deep-20260623T094131Z` | `p-min=0.12` | 384/384 | 90.301 | 82.334 | Valid improvement over 90.243, but below GPU3. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin3-pmin010-nobs-filled-long-deep-20260623T094131Z` | `n-min=3`, `p-min=0.10` | 384/384 | 89.821 | 81.719 | Valid, stricter minimum hurts. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filled-long-deep-20260623T094131Z` | `--spec-draft-threads 32` | 384/384 | **90.419** | **82.342** | New valid record; submitted to LocalMaxxing. |

Submitted record:

- LocalMaxxing ID: `cmqqgn3cm0163qo010optg91u`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filledlong512-20260623.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filledlong512-20260623.submit.log`;
- supersedes `cmqqgftv50160qo01km3s7lkt` (`90.243 tok/s`, no-backend-sampling
  without explicit draft threads).

## Takeaways

- The frontier is flat but still moving. `p-min=0.12` and draft threads 32 both
  beat the prior record, with draft threads 32 winning by about `+0.176 tok/s`.
- `n-min=3` is not useful on this prompt shape; it likely rejects too many
  low-confidence but still-correct draft continuations.
- `p-min=0.08` is below record, so the useful confidence range remains roughly
  `0.10..0.12`.
- The next sweep should switch axis: draft KV compression, batch/ubatch, polling,
  and explicit repeat of draft threads 32 for reproducibility.

## Follow-Up

Keep the promoted baseline:

```bash
MTP_N_MAX=7 MTP_N_MIN=2 MTP_P_MIN=0.10 MTP_BACKEND_SAMPLING=0 \
MTP_DRAFT_THREADS=32 BENCH_PROMPT_MODE=filled-long
```

Next four-at-a-time candidates:

- repeat the draft-threads-32 record on another GPU;
- draft `V` cache as `q8_0` only;
- draft `K/V` cache as `q8_0`;
- `BATCH_SIZE=1024` under the promoted MTP identity;
- `POLL=75` or `POLL=100` only if a slot remains.
