# 20260623T0936 N7 Backend-Sampling Sweep

Goal: test the current `n=7, n-min=2, p-min=0.10` frontier against p-split
variants and llama.cpp's draft backend sampling toggle.

Common identity:

- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, AOT BMG build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `mtp-gemma-4-26B-A4B-it.gguf`;
- flags: `BENCH_PROMPT_MODE=filled-long`, `GGML_SYCL_DISABLE_OPT=0`,
  `FLASH_ATTN=off`, `POLL=50`, `--parallel 1 --cache-ram 0`, f16 main and
  draft KV;
- quality gate: `384/384` chat canary before promotion;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

## Results

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin010-repeat-filled-long-deep-20260623T093619Z` | repeat `n=7, p-min=0.10` | 384/384 | 88.076 | 80.437 | Valid repeat, below prior 88.345 record. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin010-psplit015-filled-long-deep-20260623T093619Z` | `p-split=0.15` | 384/384 | 87.738 | 80.174 | Valid but lower; p-split remains low value. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin010-psplit005-filled-long-deep-20260623T093619Z` | `p-split=0.05` | 384/384 | 88.335 | 80.369 | Valid and near-tie, but below 88.345. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-filled-long-deep-20260623T093619Z` | `--no-spec-draft-backend-sampling` | 384/384 | **90.243** | **82.243** | New valid record; submitted to LocalMaxxing. |

Submitted record:

- LocalMaxxing ID: `cmqqgftv50160qo01km3s7lkt`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin010-nobs-filledlong512-20260623.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin010-nobs-filledlong512-20260623.submit.log`;
- supersedes `cmqqg1r0l015xqo01e6d696mx` (`88.345 tok/s`, n=7 p-min 0.10).

## Takeaways

- Disabling draft backend sampling is a clear win on this deterministic,
  low-temperature filled-long shape. It improved after-TTFT throughput from
  `88.345` to `90.243` tok/s while preserving the 384-row chat canary.
- p-split variants were not useful here. `p-split=0.05` nearly tied the old
  record, but neither `0.05`, `0.15`, nor earlier `0.20` beat plain p-min 0.10.
- The summary generator was fixed during this batch to parse the child launcher
  preamble from the server log. New summaries now capture
  `ONEAPI_DEVICE_SELECTOR`, `llama_cpp_commit`, and `llama_server`; older
  summaries may still show `oneapi_device_selector: null`.

## Follow-Up

Keep backend sampling disabled and test:

- `p-min=0.08` and `p-min=0.12`;
- `n-min=3`;
- `MTP_DRAFT_THREADS=32`;
- draft-only KV compression (`MTP_DRAFT_TYPE_V=q8_0`, then K/V q8_0 if V-only
  survives).

Treat `n=8` as exhausted unless paired with a much stricter confidence gate;
the prior n=8 run had high acceptance but too much draft overhead.
