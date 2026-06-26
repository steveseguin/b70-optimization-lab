# LocalMaxxing Submissions

Date: 2026-06-26

Model: `unsloth/gemma-4-26B-A4B-it-GGUF`, Gemma 4 26B A4B Q8 lane.

Status: active Gemma 4 Q8 B70 optimization. Keep single-replica records
separate from four independent replica aggregate capacity, and keep natural-
stop, short-prompt sustained, and filled-long sustained shapes separate.

Hardware note for the Gemma 4 26B submissions: these were run on a headless
Supermicro AMD Threadripper PRO 5955WX platform with 128 GB DDR4 and Intel Arc
Pro B70 32 GB GPUs. The current `cmqvalync02lhqr01h76rnti3` record uses one B70
replica on GPU0; the host has four B70s available for parallel single-replica
experiments.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total | Validation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-26b-a4b-q8-b70-llamacpp-syclopt0-faoff-20260623T0715` | `cmqq8phxt0103qo01afcgyjq8` | 1 | 574 | 156 | 41.806 | n/a | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-syclopt0-faoff-parallel1-cache0-20260623T0915` | `cmqq9nqbh010gqo01a9jnzl6r` | 1 | 574 | 146 | 42.154 | n/a | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-syclopt0-faoff-parallel1-cache0-long512-20260623T0945` | `cmqqa6zbx010xqo01cdtfn8e0` | 1 | 75 | 512 | 42.716 | 41.351 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n3-aot-repeat-long512-20260623T0353` | `cmqqctk4w014kqo011gyyks7r` | 1 | 75 | 512 | 48.347 | 46.602 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n3-aot-filledlong512-20260623T0853` | `cmqqexo5x0151qo0154xsie7s` | 1 | 588 | 512 | 68.192 | 63.428 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n3-aot-psplit020-filledlong512-20260623T0858` | `cmqqf759s0154qo01gwqa14uc` | 1 | 588 | 512 | 68.515 | 63.666 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n4-aot-filledlong512-20260623T0858` | `cmqqf75p70157qo018fsavf0g` | 1 | 588 | 512 | 74.395 | 68.797 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n4-aot-psplit020-filledlong512-20260623T0907` | `cmqqfe75s015aqo01xr94yxh0` | 1 | 588 | 512 | 74.498 | 68.900 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n6-aot-nmin2-pmin015-filledlong512-20260623T0912` | `cmqqfnilo015lqo011nm0q2tn` | 1 | 588 | 512 | 83.520 | 76.569 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-aot-nmin2-pmin015-filledlong512-20260623T0919` | `cmqqfv296015sqo0126mym3ko` | 1 | 588 | 512 | 87.878 | 80.252 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-aot-nmin2-pmin010-filledlong512-20260623T0925` | `cmqqg1r0l015xqo01e6d696mx` | 1 | 588 | 512 | 88.345 | 80.553 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-aot-nmin2-pmin010-nobs-filledlong512-20260623T0936` | `cmqqgftv50160qo01km3s7lkt` | 1 | 588 | 512 | 90.243 | 82.243 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filledlong512-20260623T0941` | `cmqqgn3cm0163qo010optg91u` | 1 | 588 | 512 | 90.419 | 82.342 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filledlong512-20260623T1018` | `cmqqi1p2c016jqo01vndau1y9` | 1 | 588 | 512 | 91.050 | 82.970 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filledlong512-20260623` | `cmqqkmbhr017oqo017rdfxqh2` | 1 | 588 | 512 | 91.157 | 71.057 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-c926ad098-fasttopk10-filledlong512-20260623T1508` | `cmqqsecuk01azqo018ahv0i1s` | 1 | 588 | 512 | 91.619 | 71.287 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-c926ad098-fasttopk10-cpucleanup-filledlong512-20260623T2217` | `cmqr7ni7u01gxqo01wtqsrn3u` | 1 | 588 | 512 | 91.877 first / 91.899 mean | 71.485 | 384/384 chat canary |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-c926ad098-fastargmax-cpucleanup-vmm0-ub512-poll100-filledlong512-20260623T2228` | `cmqr82niq01hgqo01v42y7ue8` | 1 | 588 | 512 | 92.397 first / 92.767 mean | 83.289 | 384/384 chat canary; conservative fresh-response headline uses first request |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-fresh-20260624T0812` | `cmqrsupdk000jqr01af3eu6vu` | 1 | 588 | 512 | 95.264 first / 95.386 mean | 81.285 | 384/384 chat canary; Q8 target/verifier with Q4_0 MTP draft only; fresh-response headline uses first request |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-directunroll7-qonly-fresh-20260624T1432` | `cmqs4jnx100k6qr01d1iy78kl` | 1 | 588 | 512 | 96.822 first / 97.226 mean | 82.462 | 384/384 chat canary; Q8 target/verifier with Q4_0 MTP draft only; direct argmax-ID unroll + q-only assistant inputs; fresh-response headline uses first request |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-directunroll7-qonly-b1024u1024-th8-fresh-20260624T1357` | `cmqs56wv100kjqr01de3fdspd` | 1 | 588 | 512 | 98.491 first / 97.886 mean | 86.194 | 384/384 chat canary; Q8 target/verifier with Q4_0 MTP draft only; direct argmax-ID unroll + q-only assistant inputs; `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`; fresh-response headline uses row 0 only |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-directunroll7-qonly-b1024u1024-th8-syclgraph0-fresh-20260624T1447` | `cmqs7uyqb00lnqr01u9dtv63r` | 1 | 588 | 512 | 98.617 first / 97.956 mean | 86.262 | 384/384 chat canary; Q8 target/verifier with Q4_0 MTP draft only; direct argmax-ID unroll + q-only assistant inputs; `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `GGML_SYCL_DISABLE_GRAPH=0`; fresh-response headline uses row 0 only |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-deferh-pmin014-fresh-20260624T1735` | `cmqsd2jpn00pwqr017fq21akz` | 1 | 588 | 512 | 101.428 first / 100.769 mean | 88.374 | 384/384 chat canary; Q8 target/verifier with Q4_0 MTP draft only; verifier row-argmax IDs + deferred target `h_nextn` + `MTP_P_MIN=0.14`; superseded by safer verifier row-argmax result; fresh-response headline uses row 0 only |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-safer-deferh-pmin014-fresh-20260624T1830` | `cmqsf630x00r1qr01d1usfo2d` | 1 | 588 | 512 | 101.482 first / 101.249 mean | 88.582 | 1536/1536 chat canary; Q8 target/verifier with Q4_0 MTP draft only; stricter verifier row-argmax shape guard + deferred target `h_nextn` + `MTP_P_MIN=0.14`; superseded by immediate-command-list result; fresh-response headline uses row 0 only, all benchmark rows `cached_tokens=0` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-safer-deferh-pmin014-immediatecl1-fresh-20260624T1932` | `cmqshlz8j00s0qr01f7lr24oh` | 1 | 588 | 512 | 101.602 first / 100.835 mean | 88.508 | 1536/1536 chat canary; Q8 target/verifier with Q4_0 MTP draft only; safer verifier row-argmax + deferred target `h_nextn` + `MTP_P_MIN=0.14` plus `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`; superseded by selected-softmax/weighted-sum result; fresh-response headline uses row 0 only, all benchmark rows `cached_tokens=0` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-selectedsoftmax-weightedsum-pmin0136-fresh-20260625T0315` | `cmqsylo2l011nqr011yydjvne` | 1 | 588 | 512 | 103.299 first / 102.193 mean | 89.849 | 1536/1536 chat canary; Q8 target/verifier with Q4_0 MTP draft only; selected-softmax + weighted-sum MoE source guards, safer verifier row-argmax, deferred target `h_nextn`, `MTP_P_MIN=0.136`, and `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`; superseded by route-cache micro-record; fresh-response headline uses row 0 only, all benchmark rows `cached_tokens=0` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-ctx8192-gpu2-pmin0136-fresh-20260626T191746` | `cmqvbq8tf02m1qr010dom0vu1` | 1 | 588 | 512 | 103.515 first / 103.193 mean | 90.220 | 1536/1536 chat canary; Q8 target/verifier with Q4_0 MTP draft only; same route-cache recipe, validated after a four-GPU CTX screen on GPU2/ctx8192; current valid fresh-response headline uses row 0 only, all benchmark rows `cached_tokens=0`; small validated micro-record over `103.301` |
| `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-pmin0136-fresh-20260626T184617` | `cmqvalync02lhqr01h76rnti3` | 1 | 588 | 512 | 103.301 first / 103.063 mean | 89.977 | 1536/1536 chat canary; Q8 target/verifier with Q4_0 MTP draft only; same selected-softmax + weighted-sum recipe plus default-off `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`; superseded by GPU2/ctx8192 route-cache validation; fresh-response headline uses row 0 only, all benchmark rows `cached_tokens=0`; micro-record only (`+0.001884 tok/s`) |

## Warmed/History Artifacts, Not Headline Records

These four rows were submitted before the fresh/warmed policy was clarified.
They are valid Q8 verification of a repeated continuation, but not valid
fresh-response speed claims because the draftless n-gram source had already
seen the benchmark output. Local queue artifacts were corrected on 2026-06-26
so top-level `tokSOut` records the cold row0 rate and warmed means live under
diagnostic `engineFlags`.

| Label | LocalMaxxing ID | GPUs | Input | Output | row0 fresh tok/s | warmed tok/s | Validation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-26b-a4b-q8-b70-llamacpp-ngrammod-24-48-64-filledlong512-20260623T1745` | `cmqqxbkzx01cxqo01j8p97627` | 1 | 588 | 512 | 41.138 | 245.980 | 384/384 chat canary; warmed/history artifact, retraction-needed |
| `gemma4-26b-a4b-q8-b70-llamacpp-ngrammod-20-32-64-filledlong512-20260623T1750` | `cmqqxjnif01d0qo01ix4oeixo` | 1 | 588 | 512 | 41.097 | 255.041 | 384/384 chat canary; warmed/history artifact, retraction-needed |
| `gemma4-26b-a4b-q8-b70-llamacpp-ngrammod-20-32-64-filledlong512-20260623T1815` | `cmqqxx7bp01dbqo012d2qiiw6` | 1 | 588 | 512 | 41.364 | 280.040 | 384/384 chat canary; warmed/history artifact, retraction-needed |
| `gemma4-26b-a4b-q8-b70-llamacpp-ngrammod-20-32-64-filledlong512-20260623T1855` | `cmqqyby6801dvqo01as3wenz2` | 1 | 588 | 512 | 41.308 | 280.642 | 384/384 chat canary; warmed/history artifact, retraction-needed |

Required packet: see
[`results/gemma4-26b-a4b-q8-b70/localmaxxing-and-targets.md`](gemma4-26b-a4b-q8-b70/localmaxxing-and-targets.md).

Submit artifacts:

- queue: `data/localmaxxing-gemma4-26b-a4b-q8-b70-syclopt0-faoff-20260623.queue.json`
- rejected first attempt: `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-syclopt0-faoff-20260623.submit.log`
- approved retry: `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-syclopt0-faoff-20260623.submit2.log`
- second approved update:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-syclopt0-faoff-parallel1-cache0-20260623.submit.log`
- sustained-decode queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-long512-20260623.queue.json`
- sustained-decode approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-long512-20260623.submit.log`
- draft-MTP short-prompt approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n3-aot-repeat-long512-20260623.submit.log`
- draft-MTP filled-long approved responses:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n3-aot-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n3-aot-psplit020-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n4-aot-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n4-aot-psplit020-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n6-aot-nmin2-pmin015-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin015-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin010-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin010-nobs-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-fasttopk10-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-fasttopk10-cpucleanup-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-c926ad098-fastargmax-cpucleanup-vmm0-ub512-poll100-filledlong512-20260623.submit.log`
- Q8-target/Q4_0-draft fresh-response approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-fresh-20260624.submit.log`
- current Q8-target/Q4_0-draft fresh-response approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-directunroll7-qonly-b1024u1024-th8-syclgraph0-fresh-20260624.submit.log`
- current row-argmax/defer-h Q8-target/Q4_0-draft fresh-response approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-deferh-pmin014-fresh-20260624.submit.log`
- current selected-softmax/weighted-sum Q8-target/Q4_0-draft fresh-response
  approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-selectedsoftmax-weightedsum-pmin0136-fresh-20260625.submit.log`
- draftless ngram-mod filled-long approved responses:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-24-48-64-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-filledlong512-20260623.submit.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-ctx4096ub512-filledlong512-20260623.submit2.log`,
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-poll100-filledlong512-20260623.submit.log`
- draftless ngram-mod filtered no-op submit artifact:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-ctx4096ub512-filledlong512-20260623.submit.log`
  (empty because the first command filtered on a non-matching label)

Correction on 2026-06-23: the four draftless ngram-mod submissions above are
not valid fresh-response headline throughput because the speedup depends on
repeated-output continuation history. They remain useful warmed/history
artifacts, but should be retracted from any public headline leaderboard view.
Their first fresh measured rows were only about `41 tok/s` after TTFT:
`41.138` (`cmqqxbkzx01cxqo01j8p97627`), `41.097`
(`cmqqxjnif01d0qo01ix4oeixo`), `41.364`
(`cmqqxx7bp01dbqo012d2qiiw6`), and `41.308`
(`cmqqyby6801dvqo01as3wenz2`). Do not average warmed repeated rows into a
fresh-response claim.
API deletion was attempted for all four IDs and returned 404 because
LocalMaxxing currently exposes only `GET/POST /api/benchmarks` and
`POST /api/benchmarks/dry-run`; see
`data/localmaxxing-responses/gemma4-ngram-history-accelerated-delete-attempts-20260623.json`
and the OpenAPI method snapshot at
`data/localmaxxing-responses/localmaxxing-openapi-benchmark-methods-20260623.json`.

The first attempt failed only because the payload used `backend="SYCL/Level Zero"`.
The accepted payload uses LocalMaxxing's enum `backend="xpu"` and stores
`SYCL/Level Zero` as `engineFlags.backendDetail`.

Date: 2026-06-23

Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`, Quark W8A8 INT8,
vLLM/XPU on Intel Arc Pro B70.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `qwen36-35b-quark-int8-b70-tp4-strict-deep-gate-20260615a13deep2` | `cmqq4mw4c00yfqo01gb2ucgxj` | 4 | 512 | 512 | 93.551 | 178.773 |
| `qwen36-35b-quark-int8-b70-tp2-safe-smoke-20260615tp2safe1` | `cmqq4mwgm00yiqo0133bj962q` | 2 | 512 | 512 | 85.869 | 162.283 |

Note: the TP4 submission is the current strict-valid deep gate: JSON `128/128`,
color `256/256`, and quality suite pass. The TP2 submission is the best safer
reference smoke with JSON `16/16` and color `16/16`; quality suite was skipped,
so it is labeled as a TP2 reference rather than a stronger deep-gate result.
Payload queue and response log:
`data/localmaxxing-qwen36-35b-quark-int8-b70-valid-2x4x-20260623.queue.json`
and
`data/localmaxxing-responses/qwen36-35b-quark-int8-b70-valid-2x4x-20260623.submit.log`.

Date: 2026-05-15

Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`, AutoRound W4A16 safetensors,
vLLM/XPU TP4.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `vllm-minimax-m27-clean-weight-piecewise-aot-p512-n1536` | `cmp6a5c1o00mpo3011hg8ncyp` | 4 | 512 | 1536 | 65.752 | 87.670 |

Note: repaired piecewise/AOT compiled path with the default-off MiniMax Q/K
RMSNorm clean-weight guard enabled. Three p512/n1536 repeats were `64.622`,
`66.659`, and `65.976` output tok/s. Raw-prompt quality canaries at 64 and
256 generated tokens both passed with `0` NUL tokens, `0` non-space control
chars, and nontrivial token diversity. This supersedes the earlier quality-
corrected `~61` tok/s TP4 baseline, but the older `~73` tok/s AOT diagnostic
remains invalid because it failed the raw corruption gate.

Date: 2026-05-09

Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`, AutoRound W4A16 safetensors, vLLM/XPU TP4.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `vllm-minimax-m27-autoround-u4-decode-p512-n128` | `cmoxptkfd00hsml01hf2ajhhp` | 4 | 512 | 128 | 29.748 | 148.742 |
| `vllm-minimax-m27-autoround-u4-decode-p512-n256` | `cmoxq7cww00i8ml019ihbeqc9` | 4 | 512 | 256 | 33.034 | 99.101 |
| `vllm-minimax-m27-autoround-u4-fp32-route-p512-n256` | `cmoy8hs3n002smk01ksgcpavr` | 4 | 512 | 256 | 34.158 | 102.474 |
| `vllm-minimax-m27-autoround-u4-pp2tp2-negative-p512-n256` | `cmoy9exmf003lmk01d3it9cz2` | 4 | 512 | 256 | 17.550 | 52.651 |
| `vllm-minimax-m27-autoround-u4-default-ipc-p512-n256` | `cmoy9qat60040mk01l5y8n3al` | 4 | 512 | 256 | 34.578 | 103.734 |
| `vllm-minimax-m27-autoround-u4-default-ipc-p512-n512` | `cmoyagit0004dmk014gk25e2k` | 4 | 512 | 512 | 37.136 | 74.272 |
| `vllm-minimax-m27-autoround-xpu-graph-fixedkv-p512-n256` | `cmoyfl7cm0057mk01suxo0glp` | 4 | 512 | 256 | 32.723 | 98.169 |

Note: unsigned llm-scaler u4 decode-only MoE path, no speculative decode, no expert dropping, no sampling changes, and no power-limit changes. The XPU graph fixed-KV result is a negative/diagnostic run: PIECEWISE graph capture succeeded with local vLLM patches, but it was slower than the non-graph default-IPC path.

Date: 2026-05-03

Model: `Lorbus/Qwen3.6-27B-int4-AutoRound`

All submitted results returned `APPROVED`.

| Label | LocalMaxxing ID | GPUs | Input | Output | tok/s out | tok/s total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `vllm-int4-single-b70-mtp-500-256` | `cmoq41b9d001alg043wsnthz2` | 1 | 500 | 256 | 45.2 | 133.44 |
| `vllm-int4-single-b70-mtp-500-512` | `cmoq47sll0005l104v3i0f9l3` | 1 | 500 | 512 | 41.3 | 81.60 |
| `vllm-int4-tp2-b70-nonmtp-500-256` | `cmoq4e9dw0002js04ledqyycn` | 2 | 500 | 256 | 49.1 | 144.88 |
| `vllm-int4-tp2-b70-nonmtp-500-512` | `cmoq4krfb000cl40456wobg7e` | 2 | 500 | 512 | 48.3 | 95.56 |
| `vllm-int4-single-b70-nonmtp-500-256` | `cmoq4r8rc0001l804tocgibus` | 1 | 500 | 256 | 31.8 | 93.80 |
| `vllm-int4-tp2-b70-mtp-500-256` | `cmoq4xppt0003ky04xidngli9` | 2 | 500 | 256 | 35.6 | 105.03 |
