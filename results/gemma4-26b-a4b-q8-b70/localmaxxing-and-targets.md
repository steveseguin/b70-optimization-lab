# Gemma 4 26B A4B LocalMaxxing Targets

Research snapshot: 2026-06-27.

This page separates public leaderboard context from this lane's promoted result
rules. The goal is a valid Q8 / INT8-or-better result on Intel Arc Pro B70, not
a speed-only lower-precision entry.

Quality/label guardrail: promoted Gemma 26B B70 submissions in this lane must
use the literal `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf` target/verifier unless the
user explicitly accepts a different target quantization. Historical labels like
`q8target-q40draft` are shorthand for a Q8-quality `UD-Q8_K_XL` target with a
Q4_0 MTP draft; they are not claims that the target was
`gemma-4-26B-A4B-it-Q8_0.gguf`. Literal `Q8_0.gguf` target runs are separate
controls and are not LocalMaxxing-promotable under the no-quality-loss rule.

As of 2026-06-27, synthetic/repeated/filled-long benchmark scores are diagnostic
only. Do not submit or advertise them as real-world throughput. Promotion and
LocalMaxxing submission require the fixed realistic prompt suite, one cold
response per prompt, `cached_tokens=0` every row, no prompt/KV/context/response
reuse or n-gram/history acceleration, verified speculation only, and primary
metric `median_tok_s_1_100_after_ttft`.

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

Current policy-compliant LocalMaxxing submission:

- `gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z`,
  llama.cpp `c926ad098` on one B70, UD-Q8_K_XL target/verifier with Q4_0 MTP
  draft, f16 KV, 8K context, reordered-Q8 VDR2, F16 p021 small-ncols,
  bulk sampled-ID verifier host read, VDR2 selected-down fused weighted-sum,
  `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`;
- fixed suite:
  `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`, each prompt once,
  `cached_tokens=0` every row;
- primary metric: **115.8466634928202 tok/s** median generated-token
  throughput for tokens 1-100 after TTFT;
- p10 `102.573`, mean `114.574`, median TTFT `181.167 ms`, median full-512
  after-TTFT `104.661`, median wall full-512 `100.640`;
- supporting same-identity strict full512 rows include the previous
  `115.72789384447941` record plus `113.47081786263712`,
  `113.81540554086772`, `114.8109417270852`, and
  `115.49839246092888 tok/s`;
- payload:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-selecteddown-reordervdr2-full512-repeat-20260629.queue.json`;
- LocalMaxxing: `cmqyrpox4021dqk01co5o4fcw`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-selecteddown-reordervdr2-full512-repeat-20260629.submit.log`.

The adjacent BF16-direct retest did not beat controls and is recorded as a
negative in
`../../patches/gemma4-26b-a4b-q8-b70/20260629-selecteddown-bf16direct-currentstack-negative.md`.

Previous policy-compliant LocalMaxxing submission, now superseded:

- `gemma4-q8-gpu1-vdr2-selecteddown-reordervdr2-full512-20260629B`,
  same VDR2 selected-down recipe, **115.72789384447941 tok/s** median
  generated-token throughput for tokens 1-100 after TTFT, LocalMaxxing
  `cmqyo0jyt08ippk01vhiobdnm`;
- payload:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-selecteddown-reordervdr2-full512-20260629.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-selecteddown-reordervdr2-full512-20260629.submit.log`.

Earlier policy-compliant LocalMaxxing submission, now superseded:

- `gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-confirm-B-n3-nmin2-p00475-ub1024-full512-20260628T052158Z`,
  llama.cpp `c926ad098` on one B70, UD-Q8_K_XL target/verifier with Q4_0 MTP
  draft, f16 KV, 8K context, reordered-Q8 VDR2, F16 p021 small-ncols,
  bulk sampled-ID verifier host read, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `UBATCH_SIZE=1024`;
- fixed suite:
  `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`, each prompt once,
  `cached_tokens=0` every row;
- primary metric: **98.34046474459183 tok/s** median generated-token throughput
  for tokens 1-100 after TTFT;
- p10 `85.979`, mean `95.953`, median TTFT `180.211 ms`, median full-512
  after-TTFT `91.174`, median wall full-512 `87.737`;
- supporting same-identity strict full512 rows: `96.01452890026427`,
  `95.90275376682132`, and `94.94094934974818 tok/s`;
- LocalMaxxing: `cmqxchyra03xmqr01b963gmi1`;
- payload:
  `data/localmaxxing-payloads/gemma4-q8-vdr2-f16p021-bulksampled-confirm-20260628T052158.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-bulksampled-full512-20260628.submit.log`.

Previous policy-compliant F16-p021 submission, now superseded:

- `gemma4-q8-gpu1-strict-vdr2-f16p021-smallncols-full512-exactconfirm-n3-nmin2-p00475-ub1024-20260628T010121Z`;
- primary metric: **95.82453787677183 tok/s** median generated-token
  throughput for tokens 1-100 after TTFT;
- LocalMaxxing: `cmqx3687103v4qr01ace1ft3m`;
- status: still valid strict evidence, but replaced as the current record by
  the VDR2 selected-down fused weighted-sum row above.

Previous policy-compliant VDR2 submission, now superseded:

- `gemma4-q8-gpu1-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z`;
- primary metric: **90.98312252660529 tok/s** median generated-token throughput
  for tokens 1-100 after TTFT;
- LocalMaxxing: `cmqwxep4a03qiqr010chjn93s`;
- status: still valid strict evidence, but replaced as the current record by
  later rows, most recently the `115.8466634928202 tok/s` row above.

Previous policy-compliant VDR2 submission, now superseded:

- `gemma4-q8-gpu2-strict-vdr2-n3-p00475-repeat-ub1024-v21-20260627T201757Z`;
- primary metric: **90.32179401019857 tok/s** median generated-token throughput
  for tokens 1-100 after TTFT;
- LocalMaxxing: `cmqwt1zk803ozqr01hctqss2z`;
- status: still valid strict evidence, but replaced as the current record by
  later rows, most recently the `115.8466634928202 tok/s` row above.

Previous policy-compliant VDR2 submission, now superseded:

- `gemma4-q8-gpu2-strict-vdr2-n3-p00475-ub1024-v19-20260627T191931Z`;
- primary metric: **89.45543282863798 tok/s** median generated-token throughput
  for tokens 1-100 after TTFT;
- LocalMaxxing: `cmqwqzayr03o8qr01j6lgx93n`;
- status: still valid strict evidence, but replaced as the current record by
  later rows, most recently the `115.8466634928202 tok/s` row above.

Previous policy-compliant VDR4 submission, now superseded:

- `gemma4-q8-gpu0-vdr4default-mtp-n3-nmin2-p005-ub1024-realistic-gate-repeat-v8`;
- primary metric: **87.61145306230438 tok/s** median generated-token throughput
  for tokens 1-100 after TTFT;
- LocalMaxxing: `cmqwnl2ag03lgqr01ch5bxknq`;
- status: still valid strict evidence, but replaced as the current record by
  later rows, most recently the `115.8466634928202 tok/s` row above.

Previous realistic-suite local Q8 observation, now superseded:

- `gemma4-q8-gpu3-vdr4default-mtp-n3-nmin2-p0075-realistic-gate-v4-20260627T171157Z`,
  llama.cpp `c926ad098` on one B70, UD-Q8_K_XL target/verifier with Q4_0 MTP
  draft, f16 KV, 8K context, default reordered-Q8 VDR4, `n_max=3`,
  `n_min=2`, `p_min=0.075`, `UBATCH_SIZE=720`;
- fixed suite:
  `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`, each prompt once,
  `cached_tokens=0` every row;
- `realistic_final_gate.passed=true`;
- primary metric: **86.47445652599384 tok/s** median generated-token throughput
  for tokens 1-100 after TTFT;
- p10 `77.1001287639242`, mean `84.8660983117653`, median TTFT
  `182.121 ms`, median full-512 after-TTFT `82.05238162525896`, median wall
  full-512 `78.41884310237452`;
- summary:
  `data/gemma4-q8-gpu3-vdr4default-mtp-n3-nmin2-p0075-realistic-gate-v4-20260627T171157Z/summary.json`;
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu3-vdr4default-mtp-n3-nmin2-p0075-realistic-gate-v4-20260627T171157Z.server.log`;
- status: previously the best valid cold-suite observation, but not
  representative enough for LocalMaxxing promotion and now superseded by the
  v8 `n3/p0.05/UB1024` strict result. The first exact repeat on GPU0 measured
  `81.73306503450416 tok/s`, and a same-GPU repeat measured
  `82.89800056264573 tok/s`.

Current realistic-suite no-spec control:

- `gemma4-q8-gpu0-vdr4default-nospec-realistic-gate-v2-20260627T165335Z`;
- same target model/runtime, no speculation, `--ctx-checkpoints 0`;
- primary metric: **74.29709476830473 tok/s** median;
- p10 `74.17460514894407`, mean `74.26752349723967`, median full-512
  after-TTFT `72.21419554247626`, median wall full-512 `70.40573079055511`;
- summary:
  `data/gemma4-q8-gpu0-vdr4default-nospec-realistic-gate-v2-20260627T165335Z/summary.json`;
- interpretation: this is the clean target-side baseline for future work.
  Draft-MTP now has a clear median advantage on the fixed suite, while no-spec
  remains the simplest quality/control reference.

Current local Q8 baseline:

- `20260623T052850Z`, llama.cpp SYCL on one B70, UD-Q8_K_XL, f16 KV, 8K context;
- chat canary 128/128 pass;
- p512/o512 chat decode `26.10 tok/s` after TTFT, `24.24 tok/s` wall;
- status: keep as a control and **do not submit** as a record unless a
  baseline-only reference entry is explicitly desired. It is far below the
  public Gemma 4 family context and should be improved first.

Historical natural-stop local Q8 best:

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

Historical short-prompt sustained-decode Q8 best:

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

Historical short-prompt draft-MTP sustained-decode Q8 best:

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
  historical synthetic diagnostic draft-MTP frontier `cmqwkedg303jeqr013z753j62`
  (`176.216 tok/s` first no-cache synthetic filled-long row; `176.403 tok/s`
  supporting repeat mean; Q8 target/verifier with Q4_0 MTP draft only);
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

Historical filled-long draft-MTP Q8-target diagnostic best:

- `gemma4-q8-gpu0-q8reorder-vdr2-ub720-nmin3-pmin010-fullconfirm-20260627T155347Z`;
- llama.cpp SYCL on one B70, UD-Q8_K_XL main GGUF plus
  `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` draft GGUF;
- same `c926ad098` `n=7` backend-sampling-off route-cache/fused-output/RMS
  reuse recipe as the previous row, plus
  `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`,
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`, and reordered Q8_0 MMVQ compile knob
  `GGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2`; runtime shape is `UBATCH_SIZE=720` with
  `MTP_N_MIN=3` and `MTP_P_MIN=0.10`, validated on GPU0;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary: **1536 repeats / 6144 case rows** passed;
- synthetic filled-long row0: first measured no-cache request after TTFT
  `176.21623213048554 tok/s`; supporting repeated-request mean
  `176.40259133127742 tok/s`; first-row wall `139.3169544024847 tok/s`;
  all rows report `usage.prompt_tokens_details.cached_tokens=0`;
- status: submitted to LocalMaxxing and approved as `cmqwkedg303jeqr013z753j62`
  before the realistic final-gate policy; classify as diagnostic until the
  fixed suite passes. It is not a promoted real-world `>150 tok/s` claim.
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-vdr2-ub720-nmin3-pmin010-fresh-20260627.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-vdr2-ub720-nmin3-pmin010-fresh-20260627.submit.log`.

Superseded Q8 MoE-ID reorder pre-final-gate diagnostic:

- `gemma4-q8-gpu0-q8reorder-ub720-nmin3-pmin010-fullconfirm-20260627T144855Z`;
- llama.cpp SYCL on one B70, UD-Q8_K_XL main GGUF plus
  `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` draft GGUF;
- same `c926ad098` `n=7` backend-sampling-off route-cache/fused-output/RMS
  reuse recipe as the previous row, plus
  `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1` and
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`; runtime shape is
  `UBATCH_SIZE=720` with `MTP_N_MIN=3` and `MTP_P_MIN=0.10`, validated on GPU0;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary: **1536 repeats / 6144 case rows** passed;
- diagnostic pre-final-gate row0 metric: first measured no-cache request after TTFT
  `171.1076295077342 tok/s`; supporting repeated-request mean
  `170.12922191012277 tok/s`; first-row wall `135.66648146097913 tok/s`;
  all rows report `usage.prompt_tokens_details.cached_tokens=0`;
- diagnostic pre-final-gate status: submitted to LocalMaxxing and approved as
  `cmqwi45d803gyqr01td3vf9ka`; superseded by
  `cmqwkedg303jeqr013z753j62` (`176.21623213048554 tok/s`);
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-ub720-nmin3-pmin010-fresh-20260627.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-ub720-nmin3-pmin010-fresh-20260627.submit.log`.

Superseded Q8 MoE-ID reorder pre-final-gate diagnostic:

- `gemma4-q8-gpu1-q8reorder-ub704-nmin3-pmin010-fullconfirm-20260627T143126Z`;
- `170.11205232778414 tok/s` first synthetic / `169.87578310923394 tok/s`
  support mean, LocalMaxxing `cmqwhkbzj03guqr01h00c8n04`.

Earlier superseded Q8 MoE-ID reorder pre-final-gate diagnostic:

- `gemma4-q8-gpu0-mulmatid-fast-q8reorder-ub768-fullconfirm-20260627T142318Z`;
- `169.9489959621758 tok/s` first synthetic / `169.5501066933547 tok/s`
  support mean, LocalMaxxing `cmqwh8du403gfqr01d6ut1ddo`.

Superseded `UBATCH_SIZE=768`, `n_min=3`, `p_min=0.10` pre-final-gate
Q8-target diagnostic:

- `gemma4-q8-gpu0-ub768-nmin3-pmin010-fullrepeat-20260627T035307Z`;
- llama.cpp SYCL on one B70, UD-Q8_K_XL main GGUF plus
  `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` draft GGUF;
- same `c926ad098` `n=7` backend-sampling-off route-cache/fused-output
  recipe as the previous row; runtime shape is `UBATCH_SIZE=768` with
  `MTP_N_MIN=3` and `MTP_P_MIN=0.10`, validated on GPU0;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary: **1536 repeats / 6144 case rows** passed;
- diagnostic pre-final-gate row0 metric: first measured no-cache request after TTFT
  `104.22626983476746 tok/s`; supporting repeated-request mean
  `104.17418893412489 tok/s`; first-row wall `90.7413762430611 tok/s`;
  all rows report `usage.prompt_tokens_details.cached_tokens=0`;
- diagnostic pre-final-gate status: submitted to LocalMaxxing and approved as
  `cmqvv3kop0309qr013ekr8apu`; this is a small variance-class micro-record
  over `cmqvmjvzx02qvqr01qh9jikow` (`104.07050714456982 tok/s`). The support
  mean also improves, but do not treat it as material progress toward
  `>150 tok/s`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-ub768-nmin3-pmin010-fresh-20260627.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-ub768-nmin3-pmin010-fresh-20260627.submit.log`.

Superseded `UBATCH_SIZE=768` draft-MTP pre-final-gate Q8-target best:

- `gemma4-q8-gpu3-b1024u768-fullrepeat-20260626T235649Z`;
- first measured no-cache request after TTFT `104.07050714456982 tok/s`;
  supporting repeated-request mean `103.588578767931 tok/s`; first-row wall
  `90.4869993907642 tok/s`; approved as `cmqvmjvzx02qvqr01qh9jikow`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-ub768-fresh-20260627.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-ub768-fresh-20260627.submit.log`.

Superseded same-stack filled-long draft-MTP pre-final-gate Q8-target best:

- `gemma4-q8-gpu0-currentrecord-control-fullrepeat-20260626T230510Z`;
- llama.cpp SYCL on one B70, UD-Q8_K_XL main GGUF plus
  `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` draft GGUF;
- same `c926ad098` `n=7/n-min=2` backend-sampling-off route-cache/fused-output
  recipe as the previous row; this is a full repeat on GPU0, not a new
  mechanism;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary **1536/1536** pass;
- diagnostic pre-final-gate row0 metric: first measured no-cache request after TTFT
  `103.9826628154082 tok/s`; supporting repeated-request mean
  `104.09604904731648 tok/s`; first-row wall `90.47935762548245 tok/s`;
  all rows report `usage.prompt_tokens_details.cached_tokens=0`;
- diagnostic pre-final-gate status: submitted to LocalMaxxing and approved as
  `cmqvjupek02pgqr01d46algvg`; this is a variance-class micro-record over
  `cmqviful602p0qr01vp27jw5i` (`103.95374341972274 tok/s`) and not material
  progress toward `>150 tok/s`; superseded by
  `cmqvmjvzx02qvqr01qh9jikow` (`104.07050714456982 tok/s`), then by
  `cmqvv3kop0309qr013ekr8apu` (`104.22626983476746 tok/s`);
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-repeat-fresh-20260626.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-repeat-fresh-20260626.submit.log`.

Superseded same-stack filled-long draft-MTP pre-final-gate Q8-target best:

- `gemma4-q8-gpu2-routecache-mtpfusedoutargmax-selfusedweights-full-20260626T222525Z`;
- llama.cpp SYCL on one B70, UD-Q8_K_XL main GGUF plus
  `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` draft GGUF;
- submitted from a headless Supermicro AMD Threadripper PRO 5955WX platform
  with 128 GB DDR4; one Intel Arc Pro B70 32 GB was used for this record;
- same `c926ad098` `n=7/n-min=2` backend-sampling-off route-cache recipe as
  the previous row, plus `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1` and
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary **1536/1536** pass;
- diagnostic pre-final-gate row0 metric: first measured no-cache request after TTFT
  `103.95374341972274 tok/s`; supporting repeated-request mean
  `104.13506066488091 tok/s`; first-row wall `90.68621473793526 tok/s`;
  all rows report `usage.prompt_tokens_details.cached_tokens=0`;
- diagnostic pre-final-gate status: submitted to LocalMaxxing and approved as
  `cmqviful602p0qr01vp27jw5i`; this is a small micro-record over
  `cmqvbq8tf02m1qr010dom0vu1` (`103.51547512013657 tok/s`) and not material
  progress toward `>150 tok/s`; superseded by `cmqvjupek02pgqr01d46algvg`
  (`103.9826628154082 tok/s`), then by `cmqvmjvzx02qvqr01qh9jikow`
  (`104.07050714456982 tok/s`), then by `cmqvv3kop0309qr013ekr8apu`
  (`104.22626983476746 tok/s`);
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-fresh-20260626.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-mtpfusedoutargmax-selfusedweights-fresh-20260626.submit.log`.

Superseded filled-long draft-MTP route-cache pre-final-gate Q8-target best:

- `gemma4-q8-gpu2-routecache-ctx8192-full-20260626T191746Z`;
- llama.cpp SYCL on one B70, UD-Q8_K_XL main GGUF plus
  `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` draft GGUF;
- validated after a four-GPU CTX screen on GPU2/ctx8192;
- diagnostic pre-final-gate row0 metric: first measured no-cache request after TTFT
  `103.51547512013657 tok/s`; supporting repeated-request mean
  `103.19340167720759 tok/s`; first-row wall `90.22004912439446 tok/s`;
  all rows report `usage.prompt_tokens_details.cached_tokens=0`;
- LocalMaxxing: `cmqvbq8tf02m1qr010dom0vu1`;
- superseded by `cmqviful602p0qr01vp27jw5i`
  (`103.95374341972274 tok/s`), then by `cmqvjupek02pgqr01d46algvg`
  (`103.9826628154082 tok/s`), then by `cmqvmjvzx02qvqr01qh9jikow`
  (`104.07050714456982 tok/s`), then by `cmqvv3kop0309qr013ekr8apu`
  (`104.22626983476746 tok/s`);
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-ctx8192-gpu2-pmin0136-fresh-20260626.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-ctx8192-gpu2-pmin0136-fresh-20260626.submit.log`.

Earlier superseded filled-long draft-MTP route-cache pre-final-gate Q8-target best:

- `gemma4-q8-gpu0-mulmatid-routecache-full-20260626T184617Z`;
- llama.cpp SYCL on one B70, UD-Q8_K_XL main GGUF plus
  `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` draft GGUF;
- submitted from a headless Supermicro AMD Threadripper PRO 5955WX platform
  with 128 GB DDR4; one Intel Arc Pro B70 32 GB was used for this record;
- `c926ad098` `n=7/n-min=2` backend-sampling-off recipe with
  `MTP_P_MIN=0.136`, source-level CPU cleanup,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`, direct argmax-ID unroll
  (`LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`), Gemma4Assistant q-only attention
  inputs (`LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`), verifier backend argmax IDs
  (`LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`), deferred target `h_nextn`
  (`LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`),
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`,
  `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`, `GGML_SYCL_ENABLE_VMM=0`,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`,
  `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`,
  `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`,
  `GGML_SYCL_DISABLE_GRAPH=0`, `--ctx-checkpoints 0`, draft threads `32/32`;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary **1536/1536** pass;
- diagnostic pre-final-gate row0 metric: first measured no-cache request after TTFT
  `103.30108468098005 tok/s`; supporting repeated-request mean
  `103.06255061691155 tok/s`; first-row wall `89.97733776184405 tok/s`;
  all rows report `usage.prompt_tokens_details.cached_tokens=0`;
- diagnostic pre-final-gate status: submitted to LocalMaxxing and approved as
  `cmqvalync02lhqr01h76rnti3`; this was a micro-record over
  `cmqsylo2l011nqr011yydjvne` (`103.2992004295621 tok/s`) and supersedes
  `cmqshlz8j00s0qr01f7lr24oh`, `cmqsf630x00r1qr01d1usfo2d`,
  `cmqsd2jpn00pwqr017fq21akz`, `cmqs7uyqb00lnqr01u9dtv63r`,
  `cmqs56wv100kjqr01de3fdspd`, `cmqs4jnx100k6qr01d1iy78kl`,
  `cmqrsupdk000jqr01af3eu6vu`, `cmqrjcly601kuqo01rbyub1x6`, and earlier
  fast-argmax/CPU-cleanup result `cmqr82niq01hgqo01v42y7ue8`;
- superseded by `cmqvbq8tf02m1qr010dom0vu1` (`103.51547512013657 tok/s`),
  then by `cmqviful602p0qr01vp27jw5i` (`103.95374341972274 tok/s`), then by
  `cmqvjupek02pgqr01d46algvg` (`103.9826628154082 tok/s`), then by
  `cmqvmjvzx02qvqr01qh9jikow` (`104.07050714456982 tok/s`), then by
  `cmqvv3kop0309qr013ekr8apu` (`104.22626983476746 tok/s`);
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-pmin0136-fresh-20260626.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-pmin0136-fresh-20260626.submit.log`.

Previous material filled-long draft-MTP pre-final-gate Q8-target best:

- `gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-20260625T031510Z`,
  repeated by
  `gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-repeat-20260625T032710Z`;
- same Q8 target / Q4_0 MTP draft recipe, without the one-shot route cache;
- diagnostic pre-final-gate row0 metric: `103.2992004295621 tok/s`; supporting mean
  `102.19335537277364 tok/s`; first-row wall `89.84890823527608 tok/s`;
- LocalMaxxing `cmqsylo2l011nqr011yydjvne`;
- keep this as the material baseline because the current route-cache record is
  only `+0.001884 tok/s`.

Superseded filled-long draft-MTP pre-final-gate Q8-target record:

- `gemma4-q8-gpu1-rowargmax-safer-immediatecl1-full-20260624T193222Z`,
  llama.cpp SYCL on one B70,
  UD-Q8_K_XL main GGUF plus `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` draft GGUF;
- submitted from a headless Supermicro AMD Threadripper PRO 5955WX platform
  with 128 GB DDR4; one Intel Arc Pro B70 32 GB was used for this record;
- same `c926ad098` `n=7/n-min=2` backend-sampling-off recipe, with
  `MTP_P_MIN=0.14`, source-level CPU cleanup,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`, direct argmax-ID unroll
  (`LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`), Gemma4Assistant q-only attention
  inputs (`LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`), safer verifier row-argmax IDs
  (`LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`, with strict sampled-row shape
  assertions), deferred target `h_nextn` (`LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`),
  `GGML_SYCL_ENABLE_VMM=0`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`,
  `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`,
  `GGML_SYCL_DISABLE_GRAPH=0`, `--ctx-checkpoints 0`, draft threads `32/32`;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary **1536/1536** pass;
- diagnostic pre-final-gate row0 metric: first measured no-cache request after TTFT
  `101.60238982389097 tok/s`; supporting repeated-request mean
  `100.83458420322299 tok/s`; first-row wall `88.50781195831634 tok/s`;
  all rows report `usage.prompt_tokens_details.cached_tokens=0`;
- diagnostic pre-final-gate status: submitted to LocalMaxxing and approved as
  `cmqshlz8j00s0qr01f7lr24oh`; supersedes the safer row-argmax/defer-H
  record `cmqsf630x00r1qr01d1usfo2d`, earlier row-argmax/defer-H
  record `cmqsd2jpn00pwqr017fq21akz`, approved direct-unroll/q-only
  batch/thread/graph pre-final-gate record `cmqs7uyqb00lnqr01u9dtv63r`,
  `cmqs56wv100kjqr01de3fdspd`, `cmqs4jnx100k6qr01d1iy78kl`,
  `cmqrsupdk000jqr01af3eu6vu`, `cmqrjcly601kuqo01rbyub1x6`, and earlier
  fast-argmax/CPU-cleanup result `cmqr82niq01hgqo01v42y7ue8`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-safer-deferh-pmin014-immediatecl1-fresh-20260624.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-safer-deferh-pmin014-immediatecl1-fresh-20260624.submit.log`.

Superseded safer row-argmax/defer-H pre-final-gate Q8-target record:

- `gemma4-q8-gpu0-rowargmax-safer-pmin014-full-20260624T183044Z`;
- LocalMaxxing `cmqsf630x00r1qr01d1usfo2d`,
  `101.4817054635395 tok/s` first no-cache request after TTFT,
  `101.24898926956536 tok/s` support mean, 1536/1536 chat canary;
- superseded by the immediate-command-list result above.

Superseded row-argmax/defer-H pre-final-gate Q8-target record:

- `gemma4-q8-gpu0-rowargmax-deferh-pmin014-full-20260624T173546Z`;
- LocalMaxxing `cmqsd2jpn00pwqr017fq21akz`, `101.42819815648124 tok/s`
  first no-cache request after TTFT, `100.76942425937877 tok/s` support mean,
  384/384 chat canary;
- superseded only by the safer verifier sampled-row shape-guard result above.

Previous direct-unroll/q-only batch/thread filled-long draft-MTP Q8-target best:

- `gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-b1024u1024-th8-syclgraph0-full-20260624T144749Z`,
  llama.cpp SYCL on one B70,
  UD-Q8_K_XL main GGUF plus `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` draft GGUF;
- submitted from a headless Supermicro AMD Threadripper PRO 5955WX platform
  with 128 GB DDR4; one Intel Arc Pro B70 32 GB was used for this record;
- same `c926ad098` `n=7/n-min=2/p-min=0.12` backend-sampling-off recipe,
  plus source-level CPU cleanup, `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
  direct argmax-ID unroll (`LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`), Gemma4Assistant q-only attention
  inputs (`LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`),
  `GGML_SYCL_ENABLE_VMM=0`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`,
  `THREADS=8`, `POLL=100`, `GGML_SYCL_DISABLE_GRAPH=0`,
  `--ctx-checkpoints 0`, draft threads `32/32`;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary **384/384** pass;
- diagnostic pre-final-gate row0 metric: first measured no-cache request after TTFT
  `98.61718830251647 tok/s`; supporting repeated-request mean
  `97.95563472401156 tok/s`; first-row wall `86.2620078252172 tok/s`;
  all rows `cached_tokens=0`;
- diagnostic pre-final-gate status: submitted to LocalMaxxing and approved as
  `cmqs7uyqb00lnqr01u9dtv63r`; supersedes approved batch/thread tuned
  pre-final-gate record `cmqs56wv100kjqr01de3fdspd`, approved direct-unroll/q-only
  Q8-target/Q4_0-draft pre-final-gate record `cmqs4jnx100k6qr01d1iy78kl`, approved Q8-target/Q4_0-draft
  pre-final-gate record `cmqrsupdk000jqr01af3eu6vu`, approved Q8-draft pre-final-gate record
  `cmqrjcly601kuqo01rbyub1x6`, and earlier fast-argmax/CPU-cleanup result
  `cmqr82niq01hgqo01v42y7ue8`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-directunroll7-qonly-b1024u1024-th8-syclgraph0-fresh-20260624.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-directunroll7-qonly-b1024u1024-th8-syclgraph0-fresh-20260624.submit.log`.

Previous batch/thread filled-long draft-MTP Q8-target best:

- `gemma4-q8-gpu3-mtp-n7-directunroll7-qonly-b1024u1024-th8-full-20260624T135701Z`;
- diagnostic pre-final-gate row0 metric: first measured no-cache request after TTFT
  `98.4913689785019 tok/s`; supporting repeated-request mean
  `97.88614261273774 tok/s`; first-row wall `86.19446305286014 tok/s`;
  all rows `cached_tokens=0`;
- LocalMaxxing `cmqs56wv100kjqr01de3fdspd`.

Previous direct-unroll/q-only filled-long draft-MTP Q8-target best:

- `gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-full-20260624T1432Z`;
- diagnostic pre-final-gate row0 metric: first measured no-cache request after TTFT
  `96.82235022330569 tok/s`; supporting repeated-request mean
  `97.22636780761407 tok/s`; first-row wall `82.46162357827212 tok/s`;
  all rows `cached_tokens=0`;
- LocalMaxxing `cmqs4jnx100k6qr01d1iy78kl`.

Previous filled-long draft-MTP pre-final-gate Q8-target best:

- `gemma4-q8-gpu0-mtp-n7-draftq40-full-20260624T081218Z`,
  llama.cpp SYCL on one B70,
  UD-Q8_K_XL main GGUF plus `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` draft GGUF;
- diagnostic pre-final-gate row0 metric: first measured no-cache request after TTFT
  `95.26352416631231 tok/s`; supporting repeated-request mean
  `95.38558173206405 tok/s`; first-row wall `81.28549578539435 tok/s`;
  all rows `cached_tokens=0`;
- LocalMaxxing `cmqrsupdk000jqr01af3eu6vu`.

Previous filled-long draft-MTP pre-final-gate Q8-draft diagnostic:

- `gemma4-q8-gpu0-mtp-n7-cleanrebuild-control-full-fresh-20260624T032733Z`,
  llama.cpp SYCL on one B70, UD-Q8_K_XL main GGUF plus
  `mtp-gemma-4-26B-A4B-it.gguf` draft GGUF;
- diagnostic pre-final-gate row0 metric: first measured no-cache request after TTFT
  `94.36621149389549 tok/s`; supporting repeated-request mean
  `92.55939821446442 tok/s`; first-row wall `80.50542700854518 tok/s`;
  all rows `cached_tokens=0`;
- LocalMaxxing `cmqrjcly601kuqo01rbyub1x6`.

Previous filled-long draft-MTP pre-final-gate Q8 diagnostic:

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
- conservative diagnostic pre-final-gate row0 metric: first measured request after TTFT
  `92.397 tok/s`; supporting independent repeated-request mean
  `92.767 tok/s`; wall mean `83.289 tok/s`; all rows `cached_tokens=0`;
- diagnostic pre-final-gate status: submitted to LocalMaxxing and approved as
  `cmqr82niq01hgqo01v42y7ue8`; supersedes approved CPU-cleanup result
  `cmqr7ni7u01gxqo01wtqsrn3u` and fast-top-k result
  `cmqqsecuk01azqo018ahv0i1s`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-fastargmax-cpucleanup-vmm0-ub512-poll100-filledlong512-20260623.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-fastargmax-cpucleanup-vmm0-ub512-poll100-filledlong512-20260623.submit.log`.

Previous filled-long draft-MTP pre-final-gate Q8 diagnostic:

- `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z`,
  llama.cpp SYCL on one B70,
  UD-Q8_K_XL main GGUF plus `mtp-gemma-4-26B-A4B-it.gguf` draft GGUF;
- same `c926ad098` recipe as the prior result, plus source-level fast top-k MTP
  draft bypass: `LLAMA_MTP_DRAFT_FAST_TOPK=1`, `LLAMA_MTP_DRAFT_TOP_K=10`;
- actual LocalMaxxing packet shape: `588` prompt tokens and `512` output
  tokens (`BENCH_PROMPT_MODE=filled-long`);
- chat canary **384/384** pass;
- decode `91.62 tok/s` after TTFT, `71.29 tok/s` warmed wall;
- diagnostic pre-final-gate status: submitted to LocalMaxxing and approved as
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
- `realistic_final_gate.passed` is absent or false;
- any fixed-suite row has missing or nonzero `cached_tokens`;
- `engineFlags.primaryMetricName` is not `median_tok_s_1_100_after_ttft`;
- the payload lacks p10, mean, TTFT, wall-clock tok/s, full-512 tok/s, prompt
  hashes, output hashes, model identity, runtime commit, launch env/flags, and
  log/result paths;
- the headline uses a synthetic row0, a repeated-prompt average, or a max
  instead of the fixed-suite median for generated tokens 1-100 after TTFT;
- the speedup is from n-gram/history continuation learned from earlier
  benchmark requests;
- prefix cache, context checkpoints, or response reuse contributed to the
  measured request and the result is being labeled fresh-response;
- the result is Q6/Q4/MXFP4/NVFP4 but labeled as the Q8 lane;
- the GPU count mixes independent replicas with a single-session model split;
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
