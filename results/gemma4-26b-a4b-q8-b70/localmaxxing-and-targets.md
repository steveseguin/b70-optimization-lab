# Gemma 4 26B A4B LocalMaxxing Targets

Research snapshot: 2026-06-23.

This page separates public leaderboard context from this lane's promoted result
rules. The goal is a valid Q8 / INT8-or-better result on Intel Arc Pro B70, not
a speed-only lower-precision entry.

## Public Target Context

Current public pages are useful as a speed target, but not as direct
quality-equivalent comparisons:

| Page | Current public top context | Why it is not directly comparable |
| --- | ---: | --- |
| `google/gemma-4-26B-A4B-it` | about `87.3 tok/s` | Rows include mixed engines, hardware, and quantization such as MXFP4/Q4. |
| `unsloth/gemma-4-26B-A4B-it-GGUF` | about `94.3 tok/s` | GGUF page, but public top rows are still mixed precision/hardware. |
| `Jackrong/Gemopus-4-26B-A4B-it-GGUF` | about `94.5 tok/s` | Fine-tune, useful idea source only; not the same checkpoint. |

Interpretation for this lane:

- A single-B70 Q8 result near or above `90 tok/s` would already be interesting.
- A lower number can still be worth keeping if it is the first validated Q8 B70
  baseline.
- Do not compare a Q8/INT8 result against MXFP4/Q4 entries as if the quality
  lane were identical.

Current local Q8 baseline:

- `20260623T052850Z`, llama.cpp SYCL on one B70, UD-Q8_K_XL, f16 KV, 8K context;
- chat canary 128/128 pass;
- p512/o512 chat decode `26.10 tok/s` after TTFT, `24.24 tok/s` wall;
- status: keep as a control and **do not submit** as a record unless a
  baseline-only reference entry is explicitly desired. It is far below the
  public Gemma 4 family context and should be improved first.

Current promoted local Q8 best:

- `gemma4-q8-gpu2-syclopt0-faoff-parallel1-cache0-deep-20260623T0915`,
  llama.cpp SYCL on one B70,
  UD-Q8_K_XL, f16 KV, 8K context;
- `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `POLL=50`,
  `--parallel 1 --cache-ram 0`, `REASONING=off`;
- chat canary **384/384** pass;
- benchmark requested `max_tokens=512`, but actual completions averaged
  `146.4` tokens because the model stopped naturally;
- p512/o512 chat decode `42.15 tok/s` after TTFT, `36.41 tok/s` wall;
- status: submitted to LocalMaxxing and approved as
  `cmqq9nqbh010gqo01a9jnzl6r`;
- queue: `data/localmaxxing-gemma4-26b-a4b-q8-b70-syclopt0-faoff-parallel1-cache0-20260623.queue.json`;
- prior approved result: `41.81 tok/s`, LocalMaxxing ID
  `cmqq8phxt0103qo01afcgyjq8`.

Current sustained-decode Q8 best:

- `gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945`,
  llama.cpp SYCL on one B70, same runtime identity as the promoted
  `parallel1-cache0` record;
- `BENCH_PROMPT_MODE=long`, which is a short instruction designed to prevent
  early stopping, not a true 512-token prompt fill;
- actual LocalMaxxing packet shape: `75` prompt tokens and `512` output tokens;
- chat canary **384/384** pass;
- decode `42.72 tok/s` after TTFT, `41.35 tok/s` wall;
- status: submitted to LocalMaxxing and approved as
  `cmqqa6zbx010xqo01cdtfn8e0`; this is a separate sustained-decode shape, not a
  direct replacement for the natural-stop/default-prompt row;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-long512-20260623.queue.json`.

Current short-prompt draft-MTP sustained-decode Q8 best:

- `gemma4-q8-gpu0-mtp-n3-aot-repeat-long-deep-20260623T0353`,
  llama.cpp SYCL on one B70,
  UD-Q8_K_XL main GGUF plus `mtp-gemma-4-26B-A4B-it.gguf` draft GGUF;
- `--spec-type draft-mtp --spec-draft-n-max 3`, draft KV `f16/f16`,
  AOT BMG build (`GGML_SYCL_DEVICE_ARCH=bmg-g31`),
  `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `POLL=50`,
  `--parallel 1 --cache-ram 0`, `REASONING=off`;
- actual LocalMaxxing packet shape: `75` prompt tokens and `512` output tokens;
- chat canary **384/384** pass;
- decode `48.35 tok/s` after TTFT, `46.60 tok/s` wall;
- status: submitted to LocalMaxxing and approved as
  `cmqqctk4w014kqo011gyyks7r`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n3-aot-repeat-long512-20260623.queue.json`.

Current filled-long draftless ngram-mod warmed/history artifact:

- `gemma4-q8-gpu1-ngram-mod-20-32-64-ctx4096ub512-poll100-ctxcp0-filled-long-deep-20260623T1855`,
  llama.cpp SYCL on one B70, UD-Q8_K_XL main GGUF, f16 KV;
- `--spec-type ngram-mod --ctx-checkpoints 0 --spec-ngram-mod-n-match 20
  --spec-ngram-mod-n-min 32 --spec-ngram-mod-n-max 64`, AOT BMG build,
  llama.cpp `c926ad098`, `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`,
  `POLL=100`, `--parallel 1 --cache-ram 0`, `CTX_SIZE=4096`,
  `UBATCH_SIZE=512`;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary **384/384** pass;
- decode `280.64 tok/s` after TTFT, `206.24 tok/s` warmed wall;
- server log: `3493/3493` accepted/generated n-gram draft tokens, mean accepted
  length `63.38`;
- status: submitted to LocalMaxxing before the fresh/warmed rule clarification
  and approved as `cmqqyby6801dvqo01as3wenz2`; **retraction-needed if
  displayed as normal headline throughput**. It supersedes prior warmed/history
  ngram rows only:
  `cmqqxx7bp01dbqo012d2qiiw6` (`280.04 tok/s`),
  `cmqqxjnif01d0qo01ix4oeixo` (`255.04 tok/s`) and
  `cmqqxbkzx01cxqo01j8p97627` (`245.98 tok/s`). It does **not** supersede the
  current fresh-response draft-MTP record `cmqrsupdk000jqr01af3eu6vu`
  (`95.264 tok/s` first no-cache request; `95.386 tok/s` supporting repeat
  mean; Q8 target/verifier with Q4_0 MTP draft only);
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-poll100-filledlong512-20260623.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-poll100-filledlong512-20260623.submit.log`;
- caveat: this is history-cache acceleration on a repetitive sustained-decode
  benchmark. It is quality-preserving because every drafted token is verified by
  the Q8 target model, but it should not be described as unique-prompt no-cache
  decode throughput or a 32K-context result. API deletion was attempted for all
  four submitted ngram rows on 2026-06-23, but LocalMaxxing exposes no
  documented benchmark delete endpoint and `DELETE /api/benchmarks/<id>`
  returned 404; see
  `data/localmaxxing-responses/gemma4-ngram-history-accelerated-delete-attempts-20260623.json`
  and
  `data/localmaxxing-responses/localmaxxing-openapi-benchmark-methods-20260623.json`.

Current filled-long draft-MTP fresh-response Q8-target best:

- `gemma4-q8-gpu0-mtp-n7-draftq40-full-20260624T081218Z`,
  llama.cpp SYCL on one B70,
  UD-Q8_K_XL main GGUF plus `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` draft GGUF;
- same `c926ad098` `n=7/n-min=2/p-min=0.12` backend-sampling-off recipe,
  plus source-level CPU cleanup, `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
  `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`, `POLL=100`,
  `--ctx-checkpoints 0`, draft threads `32/32`;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary **384/384** pass;
- fresh-response headline: first measured no-cache request after TTFT
  `95.26352416631231 tok/s`; supporting repeated-request mean
  `95.38558173206405 tok/s`; first-row wall `81.28549578539435 tok/s`;
  all rows `cached_tokens=0`;
- fresh-response status: submitted to LocalMaxxing and approved as
  `cmqrsupdk000jqr01af3eu6vu`; supersedes approved Q8-draft fresh record
  `cmqrjcly601kuqo01rbyub1x6` and earlier fast-argmax/CPU-cleanup result
  `cmqr82niq01hgqo01v42y7ue8`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-fresh-20260624.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-fresh-20260624.submit.log`.

Previous filled-long draft-MTP fresh-response Q8-draft best:

- `gemma4-q8-gpu0-mtp-n7-cleanrebuild-control-full-fresh-20260624T032733Z`,
  llama.cpp SYCL on one B70, UD-Q8_K_XL main GGUF plus
  `mtp-gemma-4-26B-A4B-it.gguf` draft GGUF;
- fresh-response headline: first measured no-cache request after TTFT
  `94.36621149389549 tok/s`; supporting repeated-request mean
  `92.55939821446442 tok/s`; first-row wall `80.50542700854518 tok/s`;
  all rows `cached_tokens=0`;
- LocalMaxxing `cmqrjcly601kuqo01rbyub1x6`.

Previous filled-long draft-MTP fresh-response Q8 best:

- `gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z`,
  llama.cpp SYCL on one B70,
  UD-Q8_K_XL main GGUF plus `mtp-gemma-4-26B-A4B-it.gguf` draft GGUF;
- same `c926ad098` `n=7/n-min=2/p-min=0.12` backend-sampling-off recipe,
  plus source-level CPU cleanup, `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
  `LLAMA_MTP_DRAFT_FAST_TOPK=0`, `GGML_SYCL_ENABLE_VMM=0`,
  `UBATCH_SIZE=512`, and `POLL=100`;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary **384/384** pass;
- conservative fresh-response headline: first measured request after TTFT
  `92.397 tok/s`; supporting independent repeated-request mean
  `92.767 tok/s`; wall mean `83.289 tok/s`; all rows `cached_tokens=0`;
- fresh-response status: submitted to LocalMaxxing and approved as
  `cmqr82niq01hgqo01v42y7ue8`; supersedes approved CPU-cleanup result
  `cmqr7ni7u01gxqo01wtqsrn3u` and fast-top-k result
  `cmqqsecuk01azqo018ahv0i1s`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-fastargmax-cpucleanup-vmm0-ub512-poll100-filledlong512-20260623.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-fastargmax-cpucleanup-vmm0-ub512-poll100-filledlong512-20260623.submit.log`.

Previous filled-long draft-MTP fresh-response Q8 best:

- `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z`,
  llama.cpp SYCL on one B70,
  UD-Q8_K_XL main GGUF plus `mtp-gemma-4-26B-A4B-it.gguf` draft GGUF;
- same `c926ad098` recipe as the prior result, plus source-level fast top-k MTP
  draft bypass: `LLAMA_MTP_DRAFT_FAST_TOPK=1`, `LLAMA_MTP_DRAFT_TOP_K=10`;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary **384/384** pass;
- decode `91.62 tok/s` after TTFT, `71.29 tok/s` warmed wall;
- fresh-response status: submitted to LocalMaxxing and approved as
  `cmqqsecuk01azqo018ahv0i1s`; superseded by the CPU-cleanup and fast-argmax
  records above. It superseded approved result `cmqqkmbhr017oqo017rdfxqh2`
  (`91.16 tok/s`);
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-fasttopk10-filledlong512-20260623.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-fasttopk10-filledlong512-20260623.submit.log`.

Previous filled-long draft-MTP sustained-decode Q8 best:

- `gemma4-q8-gpu0-mtp-n7-latest-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T113058Z`,
  llama.cpp SYCL on one B70,
  UD-Q8_K_XL main GGUF plus `mtp-gemma-4-26B-A4B-it.gguf` draft GGUF;
- `--spec-type draft-mtp --spec-draft-n-max 7 --spec-draft-n-min 2
  --spec-draft-p-min 0.12 --no-spec-draft-backend-sampling
  --spec-draft-threads 32 --spec-draft-threads-batch 32`,
  `--ctx-checkpoints 0`, draft KV `f16/f16`, AOT BMG build
  (`GGML_SYCL_DEVICE_ARCH=bmg-g31`), llama.cpp `c926ad098`,
  `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `POLL=50`,
  `--parallel 1 --cache-ram 0`, `REASONING=off`;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary **384/384** pass;
- decode `91.16 tok/s` after TTFT, `71.06 tok/s` warmed wall;
- status: submitted to LocalMaxxing and approved as
  `cmqqkmbhr017oqo017rdfxqh2`; superseded by the fast-top-k result above.
  It had superseded approved result
  `cmqqi1p2c016jqo01vndau1y9` (`91.05 tok/s`);
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filledlong512-20260623.queue.json`.

Previous draft-MTP approved result:

- `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T101814Z`,
  `91.05 tok/s` after TTFT on the filled-long shape, approved as
  `cmqqi1p2c016jqo01vndau1y9`.
- `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filled-long-deep-20260623T094131Z`,
  `90.42 tok/s` after TTFT on the filled-long shape, approved as
  `cmqqgn3cm0163qo010optg91u`.
- `gemma4-q8-gpu1-mtp-n3-long-deep-20260623T0328`, `46.36 tok/s` after TTFT,
  approved as `cmqqbyv5w013vqo019pmp161f`;
- `gemma4-q8-gpu0-mtp-n3-repeat-long-deep-20260623T0337`, `47.63 tok/s` after
  TTFT, approved as `cmqqc99m2014cqo01s5t61bs6`;
- `gemma4-q8-gpu3-mtp-n3-aot-bmg-long-deep-20260623T0345`, `47.92 tok/s` after
  TTFT, approved as `cmqqcje2r014fqo01e8rrgwwr`;
- `gemma4-q8-gpu1-mtp-n4-long-deep-20260623T1140`, `44.50 tok/s` after TTFT,
  approved as `cmqqblfw30132qo01jbi1svnu`.
- `gemma4-q8-gpu3-mtp-n3-aot-filled-long-deep-20260623T085322Z`,
  `68.19 tok/s` after TTFT on the filled-long shape, approved as
  `cmqqexo5x0151qo0154xsie7s`;
- `gemma4-q8-gpu2-mtp-n3-aot-psplit020-filled-long-deep-20260623T085844Z`,
  `68.51 tok/s` after TTFT on the filled-long shape, approved as
  `cmqqf759s0154qo01gwqa14uc`.
- `gemma4-q8-gpu3-mtp-n4-aot-filled-long-deep-20260623T085822Z`,
  `74.39 tok/s` after TTFT on the filled-long shape, approved as
  `cmqqf75p70157qo018fsavf0g`.
- `gemma4-q8-gpu1-mtp-n4-aot-psplit020-filled-long-deep-20260623T090712Z`,
  `74.50 tok/s` after TTFT on the filled-long shape, approved as
  `cmqqfe75s015aqo01xr94yxh0`.
- `gemma4-q8-gpu2-mtp-n6-aot-nmin2-pmin015-filled-long-deep-20260623T091227Z`,
  `83.52 tok/s` after TTFT on the filled-long shape, approved as
  `cmqqfnilo015lqo011nm0q2tn`.
- `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin015-filled-long-deep-20260623T091939Z`,
  `87.88 tok/s` after TTFT on the filled-long shape, approved as
  `cmqqfv296015sqo0126mym3ko`.
- `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin010-filled-long-deep-20260623T092524Z`,
  `88.35 tok/s` after TTFT on the filled-long shape, approved as
  `cmqqg1r0l015xqo01e6d696mx`.

## Submission Packet

LocalMaxxing requires at minimum:

- `hfId`;
- `hardware`;
- `engineName`;
- `quantization`;
- `tokSOut`;
- at least one secondary metric: `tokSPrefill`, `tokSTotal`, `ttftMs`, or
  `peakVramGb`.

Useful optional fields for this repo's records:

- `modelRevision`;
- `engineVersion`;
- `backend`;
- `promptTokens`;
- `outputTokens`;
- `contextLength`;
- `batchSize`;
- `engineFlags`;
- `notes`.

The API supports a dry-run endpoint before writing a real benchmark. The local
helper reads the key from `LMX_API_KEY` or
`/home/steve/.config/localmaxxing/api_key`; never put that key in a payload,
note, shell history snippet, or commit.

## Gemma 4 Payload Shape

For the primary GGUF lane:

```text
hfId: unsloth/gemma-4-26B-A4B-it-GGUF
modelRevision: 3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a
engineName: llama.cpp
backend: sycl/xpu
quantization: UD-Q8_K_XL
hardware.hwClass: DISCRETE_GPU
hardware.gpuName: Intel Arc Pro B70
hardware.vramGb: 32
hardware.gpuCount: 1 for a single-replica record, 4 only for aggregate service records
```

Engine flags should include the command snippet and the relevant values from
the server log:

- llama.cpp commit;
- `CTX_SIZE`;
- `BATCH_SIZE`;
- `UBATCH_SIZE`;
- `CACHE_TYPE_K` / `CACHE_TYPE_V`;
- `GGML_SYCL_DISABLE_OPT`;
- `GGML_SYCL_DISABLE_GRAPH`;
- `GGML_SYCL_DISABLE_DNN`;
- `ONEAPI_DEVICE_SELECTOR`;
- `-fa` state;
- benchmark prompt mode and actual prompt/output token counts;
- MTP/spec flags if enabled.
- source-level experimental MTP knobs if enabled, including
  `LLAMA_MTP_DRAFT_FAST_TOPK`, `LLAMA_MTP_DRAFT_TOP_K`, and
  `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN`.

## Do Not Submit If

- any chat canary fails;
- only raw `/v1/completions` was tested;
- `usage.completion_tokens` is missing and output token count was guessed;
- the result is Q6/Q4/MXFP4/NVFP4 but labeled as the Q8 lane;
- a speed win comes from a config family with unresolved nondeterministic
  failures;
- the model file, runtime commit, or launch identity is incomplete.

## Source Links

- LocalMaxxing API docs: <https://www.localmaxxing.com/en/api-docs>
- Google model page:
  <https://www.localmaxxing.com/en/models/google/gemma-4-26B-A4B-it>
- Unsloth GGUF model page:
  <https://localmaxxing.com/en/models/unsloth/gemma-4-26B-A4B-it-GGUF>
- LocalMaxxing CLI:
  <https://github.com/LottoLottoLotto/localmaxxing-cli>
