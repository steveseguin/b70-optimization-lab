# Gemma 4 Q8 c926 interaction batch

Date: 2026-06-23
Owner/agent: Codex

## Hypothesis

Test the remaining strongest post-record interactions recommended by the result
audit:

- `p-min=0.115`, which had pre-c926 near-miss evidence;
- `--no-kv-unified + draft_threads_batch=28`, combining the strongest post-c926
  neighbor with the best unported draft-thread near-miss;
- `--no-kv-unified + p-min=0.115`;
- `POLL=100 + draft_threads_batch=28`.

This batch used the diagnostic-timing llama.cpp build, but `LLAMA_MTP_TIMING`
was unset. Treat as a full-gate screen; any winner would require a clean
baseline rerun before promotion.

## Shared Identity

- runtime: `/home/steve/src/llama.cpp-latest-gemma`, llama.cpp `c926ad098`,
  version `9769`, with the diagnostic timing patch compiled in but disabled;
- model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/mtp-gemma-4-26B-A4B-it.gguf`;
- one full model replica per B70 via `ONEAPI_DEVICE_SELECTOR=level_zero:<gpu>`;
- common MTP: `n-max=7`, `n-min=2`, backend sampling off,
  draft threads `32`, draft KV `f16/f16`;
- common extra args: `--parallel 1 --cache-ram 0 --ctx-checkpoints 0`;
- shape: `BENCH_PROMPT_MODE=filled-long`, `588` prompt tokens / `512`
  completion tokens;
- gate: chat canary `96` repeats x `4` cases = `384/384`.

## Results

| Variant | Gate | tok/s after TTFT | wall tok/s | TTFT s | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `pmin0115` | 384/384 | 90.260116 | 70.475475 | 1.592554 | Loss |
| `nokvunified-dtb28` | 384/384 | 89.456705 | 69.829384 | 1.608799 | Loss |
| `nokvunified-pmin0115` | 384/384 | 90.243924 | 70.427496 | 1.596409 | Loss |
| `poll100-dtb28` | 384/384 | 90.248426 | 70.414374 | 1.598084 | Loss |

Current record remains:

- `gemma4-q8-gpu0-mtp-n7-latest-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T113058Z`
- `91.156717 tok/s` after TTFT, `384/384`, LocalMaxxing
  `cmqqkmbhr017oqo017rdfxqh2`.

## Artifacts

- `data/gemma4-q8-gpu0-mtp-n7-latest-c926ad098-pmin0115-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T124603Z/summary.json`
- `data/gemma4-q8-gpu1-mtp-n7-latest-c926ad098-nokvunified-dtb28-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T124603Z/summary.json`
- `data/gemma4-q8-gpu2-mtp-n7-latest-c926ad098-nokvunified-pmin0115-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T124603Z/summary.json`
- `data/gemma4-q8-gpu3-mtp-n7-latest-c926ad098-poll100-dtb28-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T124603Z/summary.json`

## Decision

No LocalMaxxing submission. All four are valid quality-passing losses and sit
inside the existing `~90 tok/s` repeat cluster.
