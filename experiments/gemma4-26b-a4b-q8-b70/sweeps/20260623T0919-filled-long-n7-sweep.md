# 20260623T0919 Filled-Long N7 Sweep

Goal: follow the `83.52 tok/s` `n=6, n-min=2, p-min=0.15` win with a focused
near-neighbor sweep. The sweep tested n=6 reproducibility, n=6 confidence
thresholds, and a first n=7 probe.

Common identity:

- repo: `/home/steve/qwen36-results-main`;
- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, AOT BMG build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- model: `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/mtp-gemma-4-26B-A4B-it.gguf`;
- flags: `BENCH_PROMPT_MODE=filled-long`, `GGML_SYCL_DISABLE_OPT=0`,
  `FLASH_ATTN=off`, `POLL=50`, `--parallel 1 --cache-ram 0`, f16 main and
  draft KV;
- quality gate: `CANARY_REPEATS=96`, four chat cases, `384/384` required;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

## Results

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n6-aot-nmin2-pmin015-repeat-filled-long-deep-20260623T091939Z` | repeat `n=6, n-min=2, p-min=0.15` | 384/384 | 83.952 | 76.923 | Valid repeat, slightly above prior n=6 record but superseded by n=7. |
| 1 | `gemma4-q8-gpu1-mtp-n6-aot-nmin2-pmin010-filled-long-deep-20260623T091939Z` | `n=6, p-min=0.10` | 384/384 | 83.987 | 77.009 | Best n=6 so far, but superseded by n=7. |
| 2 | `gemma4-q8-gpu2-mtp-n6-aot-nmin2-pmin020-filled-long-deep-20260623T091939Z` | `n=6, p-min=0.20` | 384/384 | 83.684 | 76.733 | Valid but no improvement. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin015-filled-long-deep-20260623T091939Z` | `n=7, n-min=2, p-min=0.15` | 384/384 | **87.878** | **80.252** | New valid record; submitted to LocalMaxxing. |

## Submitted Record

- LocalMaxxing ID: `cmqqfv296015sqo0126mym3ko`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin015-filledlong512-20260623.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin015-filledlong512-20260623.submit.log`;
- supersedes `cmqqfnilo015lqo011nm0q2tn` (`83.520 tok/s`, n=6 gated).

## Takeaways

- `n=6` is reproducible in the `83.5-84.0 tok/s` band. p-min changes from
  `0.10` to `0.20` moved throughput by less than half a tok/s.
- `n=7, n-min=2, p-min=0.15` produced a clear step up to `87.88 tok/s` while
  preserving the 384-row chat canary.
- The current frontier should stay at n=7/n=8 before changing runtime families.
  The next sweep is already focused on n=7 p-min variants plus n=8 gated.

## Next Sweep

- repeat `n=7, n-min=2, p-min=0.15`;
- `n=7, n-min=2, p-min=0.10`;
- `n=7, n-min=2, p-min=0.20`;
- `n=8, n-min=2, p-min=0.15`.

Submit only if a candidate beats `87.878 tok/s` and passes the 384-row canary.
