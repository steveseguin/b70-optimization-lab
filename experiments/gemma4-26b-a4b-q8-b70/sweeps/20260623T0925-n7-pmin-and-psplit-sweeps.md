# 20260623T0925 N7 P-Min And P-Split Sweeps

Goal: tune the `n=7` filled-long frontier after the `87.878 tok/s` p-min 0.15
record. This batch tested p-min variants, n=8, and p-split interaction.

Common successful-run identity:

- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, AOT BMG build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `mtp-gemma-4-26B-A4B-it.gguf`;
- flags: `BENCH_PROMPT_MODE=filled-long`, `GGML_SYCL_DISABLE_OPT=0`,
  `FLASH_ATTN=off`, `POLL=50`, `--parallel 1 --cache-ram 0`, f16 main and
  draft KV;
- quality gate: `384/384` chat canary before promotion;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

## 0925 Sweep

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin015-repeat-filled-long-deep-20260623T092524Z` | repeat `n=7, p-min=0.15` | no summary | n/a | n/a | Startup hang before readiness; preserved as negative artifact. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin010-filled-long-deep-20260623T092524Z` | `n=7, p-min=0.10` | 384/384 | **88.345** | **80.553** | New valid record; submitted to LocalMaxxing. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin020-filled-long-deep-20260623T092524Z` | `n=7, p-min=0.20` | no summary | n/a | n/a | Startup hang before readiness; preserved as negative artifact. |
| 3 | `gemma4-q8-gpu3-mtp-n8-aot-nmin2-pmin015-filled-long-deep-20260623T092524Z` | `n=8, p-min=0.15` | 384/384 | 60.782 | 56.980 | Valid but large regression; n=8 has too much draft overhead on this path. |

Submitted record:

- LocalMaxxing ID: `cmqqg1r0l015xqo01e6d696mx`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin010-filledlong512-20260623.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin010-filledlong512-20260623.submit.log`;
- supersedes `cmqqfv296015sqo0126mym3ko` (`87.878 tok/s`, n=7 p-min 0.15).

## 0931 Opportunistic Sweep

After the n=8 and p-min 0.10 runs completed, GPU1 and GPU3 were reused while
the two hung 0925 startup attempts were still being investigated.

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin005-filled-long-deep-20260623T093120Z` | `n=7, p-min=0.05` | 384/384 | 87.376 | 79.641 | Valid but lower than p-min 0.10. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-psplit020-filled-long-deep-20260623T093120Z` | `n=7, p-min=0.10, p-split=0.20` | 384/384 | 88.313 | 80.657 | Valid, close to record but slightly below after-TTFT. |

## Takeaways

- `p-min=0.10` is the current best confidence gate for n=7.
- Lowering p-min to `0.05` hurt throughput, and raising n to `8` was a clear
  loss despite high acceptance length. The n=8 final stats showed more draft
  generation cost than the extra accepted token could pay back.
- `p-split=0.20` nearly tied the record and slightly improved wall throughput,
  but did not beat after-TTFT throughput. It is still worth testing
  `p-split=0.05/0.15` around `p-min=0.10`.
- Two 0925 startup attempts hung before readiness with only early memory-fitting
  logs and empty `models.json`. They were killed and kept as negative artifacts.
  Do not over-interpret those as correctness failures; they look like transient
  launch/resource hangs.

## Follow-Up

The next sweep tests:

- repeat `n=7, p-min=0.10`;
- `n=7, p-min=0.10, p-split=0.15`;
- `n=7, p-min=0.10, p-split=0.05`;
- `n=7, p-min=0.10, --no-spec-draft-backend-sampling`.

The alternate Q8_0 GGUF finished downloading at
`/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-Q8_0.gguf`
(`26,859,859,744` bytes). Test it only after the current Q8_K_XL MTP frontier
is no longer moving, because Q8_K_XL is already producing validated records.
