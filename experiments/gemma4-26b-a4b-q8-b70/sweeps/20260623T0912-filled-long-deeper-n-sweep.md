# 20260623T0912 Filled-Long Deeper MTP Sweep

Goal: push beyond the `n=4 + p-split=0.20` filled-long record on one Intel
Arc Pro B70 while preserving Q8-quality weights and the 384-row chat canary.

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
| 0 | `gemma4-q8-gpu0-mtp-n4-aot-psplit020-repeat-filled-long-deep-20260623T091227Z` | repeat prior `n=4 + p-split=0.20` record | 384/384 | 74.088 | 68.507 | Valid repeat, below prior 74.498 record. |
| 1 | `gemma4-q8-gpu1-mtp-n5-aot-filled-long-deep-20260623T091227Z` | raise to `--spec-draft-n-max 5` with no extra gate | 384/384 | 78.639 | 72.254 | Valid improvement over n=4, but superseded by n=6 gated. |
| 2 | `gemma4-q8-gpu2-mtp-n6-aot-nmin2-pmin015-filled-long-deep-20260623T091227Z` | `--spec-draft-n-max 6 --spec-draft-n-min 2 --spec-draft-p-min 0.15` | 384/384 | **83.520** | **76.569** | New valid record; submitted to LocalMaxxing. |
| 3 | `gemma4-q8-gpu3-mtp-n4-aot-psplit020-b1024-filled-long-deep-20260623T091227Z` | repeat n=4 p-split with `BATCH_SIZE=1024` | 384/384 | 74.419 | 68.800 | Valid, no meaningful gain over prior n=4. |

## Submitted Record

- LocalMaxxing ID: `cmqqfnilo015lqo011nm0q2tn`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n6-aot-nmin2-pmin015-filledlong512-20260623.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n6-aot-nmin2-pmin015-filledlong512-20260623.submit.log`;
- supersedes `cmqqfe75s015aqo01xr94yxh0` (`74.498 tok/s`, n=4 p-split).

## Takeaways

- The filled-long prompt shape benefits from deeper MTP than the short-prompt
  `75/512` shape. Prior short-prompt tests found `n=5/6` worse, but the
  `588/512` filled-long record improved from `74.50` to `83.52` tok/s.
- Confidence gating matters at higher depth. The first strong win was
  `n=6, n-min=2, p-min=0.15`; keep p-min sweeps around this point before
  branching to different runtimes.
- `BATCH_SIZE=1024` did not move the n=4 p-split lane; do not prioritize batch
  size until MTP depth/gating is exhausted.

## Next Sweep

Run four independent replicas around the new winner:

- repeat `n=6, n-min=2, p-min=0.15`;
- `n=6, n-min=2, p-min=0.10`;
- `n=6, n-min=2, p-min=0.20`;
- `n=7, n-min=2, p-min=0.15`.

Submit only if a candidate beats `83.520 tok/s` and passes the 384-row canary.
