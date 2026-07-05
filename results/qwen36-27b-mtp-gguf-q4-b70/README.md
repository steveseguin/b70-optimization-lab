# Qwen3.6 27B MTP GGUF Q4 on B70

This result packet is reserved for the Unsloth Qwen3.6 27B MTP GGUF Q4 lane on
Intel Arc Pro B70.

## Status

Bring-up and the first strict fresh-response sweep are complete. The lane is
valid but **not competitive** with the Intel AutoRound vLLM/XPU lane.

Best strict GGUF row so far:

- `Qwen3.6-27B-UD-Q4_K_XL.gguf`, llama.cpp/SYCL `9860 (fdb1db877)`,
  one B70, one server slot (`-np 1`), FlashAttention on, f16 KV,
  `draft-mtp`, `n_max=3`, `n_min=0`, `p_min=0.00`, `ctx=4096`,
  `batch=1024`, `ubatch=256`, `--ctx-checkpoints 0`;
- fixed Qwen realistic suite, each prompt once, `cached_tokens=0` on all
  requests, no prompt/KV/context checkpoint/history reuse;
- latest cache-off/selector-fixed refresh:
  median `30.812 tok/s` for generated tokens 1-100 after TTFT, p10 `27.982`,
  mean `30.668`, full-output median `30.393`, TTFT median `419.0 ms`;
- evidence:
  `../../data/qwen36-27b-mtp-gguf-q4-b70-baselines/qwen36-27b-udq4xl-gguf-llamacpp-mtp3-faon-cacheoff-qwensuite128-20260705T224527Z.json`;
- original 2026-07-03 support row:
  `../../data/qwen36-27b-mtp-gguf-q4-b70-baselines/llamacpp-mtp3-aot-np1-realistic128-20260703T060748Z.json`
  at `30.679 tok/s`;
- compact sweep ledger:
  `initial-realistic-sweep-20260703.json`.
- LocalMaxxing reference:
  `cmr6mn5ct0076mn01on3dnpyn`, submitted as a valid but non-competitive
  model/runtime variation; queue and response are
  `../../experiments/qwen36-27b-mtp-gguf-q4-b70/localmaxxing/qwen36-27b-gguf-q4-mtp3-20260703.queue.json`
  and
  `../../data/localmaxxing-responses/qwen36-27b-gguf-q4-mtp3-20260703.submit.log`.

The current valid INT4/Q4 Qwen27 headline remains the separate vLLM/XPU
AutoRound lane. The fastest quality-gated practical row is
`webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head (BF16 scales)` at
median `65.276 tok/s` on the fixed Qwen realistic suite. The older Intel
checkpoint promote-source row is `53.522 tok/s`.

`../qwen36-27b-autoround-int4-b70/README.md`

## Identity

- Model repo: `unsloth/Qwen3.6-27B-MTP-GGUF`
- Target file: `Qwen3.6-27B-UD-Q4_K_XL.gguf`
- Runtime: llama.cpp/SYCL
- Hardware: one Intel Arc Pro B70 per replica first
- Build: `/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp`
- Experiment lane:
  `../../experiments/qwen36-27b-mtp-gguf-q4-b70/README.md`

## Initial Sweep Outcome

All rows below passed the realistic final gate with `cached_tokens=0`, but none
beat the vLLM AutoRound record:

| Label | Median tok/s | Outcome |
| --- | ---: | --- |
| `mtp3` default | `30.679` | best GGUF row so far |
| `mtp3,n_min=2,p_min=0.0475` | `30.342` | no win |
| `mtp3,q8_0 KV` | `30.323` | no win; separate quality mode if revisited |
| `mtp3,ubatch=1024` | `30.268` | no win |
| `mtp3,VMM=0` | `30.124` | no win |
| `mtp3,ubatch=1024,poll=100,immediate CL` | `30.082` | no win |
| `mtp3,ubatch=512` | `30.008` | no win |
| `mtp3,FlashAttention off` | `29.723` | no win; TTFT worsened |
| `mtp4` | `27.931` | no win; acceptance falls |
| `mtp5` | `25.403` | no win; acceptance falls further |
| no spec | `23.567` | control |

Interpretation: llama.cpp MTP helps this GGUF (`30.7` vs `23.6 tok/s`) but the
target path itself is too slow compared with vLLM AutoRound. Config-only GGUF
tuning is low priority unless a source-level llama.cpp Qwen/GDN optimization or
a materially different GGUF quant appears.

## 2026-07-05 Refresh

This refresh fixed local harness defaults rather than changing the runtime:

- `serve-qwen36-27b-mtp-gguf-llamacpp.sh` and the generic rapid llama.cpp
  server wrapper now default to `ONEAPI_DEVICE_SELECTOR=level_zero:*` plus
  `ZE_AFFINITY_MASK=$GPU_INDEX`. The previous `level_zero:$GPU_INDEX` selector
  can fail device discovery in a fresh shell.
- Qwen GGUF benchmark wrappers now default to
  `REQUEST_EXTRA_JSON='{"cache_prompt":false}'`; strict rows also pass
  `--cache-ram 0` to the server. The gate verified `cached_tokens=0` on every
  row.
- Model checksum:
  `4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095`.

Validated same-suite rows:

| Label | Median tok/s | p10 | mean | TTFT ms | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| one-off MTP3 refresh | `30.812` | `27.982` | `30.668` | `419.0` | best current support row |
| four-way MTP3 | `29.514` | `26.607` | `29.718` | `423.2` | support / variance |
| four-way MTP4 | `28.599` | `24.305` | `28.005` | `422.7` | no win |
| four-way MTP5 | `24.904` | `22.471` | `25.057` | `423.9` | no win |
| four-way no-spec | `23.675` | `23.424` | `23.646` | `411.0` | control |

Follow-up p-min/deeper-MTP screen after fixing the cache-off JSON wrapper:

| Label | Median tok/s | p10 | mean | TTFT ms | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| MTP5, `n_min=1`, `p_min=0.75` | `31.040` | `29.144` | `31.203` | `421.0` | no win versus vLLM |
| MTP7, `n_min=1`, `p_min=0.75` | `30.990` | `28.869` | `30.921` | `428.0` | no win |
| MTP7, `n_min=1`, `p_min=0.65` | `31.480` | `29.492` | `31.751` | `424.7` | best p-min row, still noncompetitive |
| MTP9, `n_min=2`, `p_min=0.75` | `27.312` | `24.493` | `27.712` | `427.3` | regression |

Conclusion unchanged: Qwen27 GGUF/llama.cpp is valid and useful as a
same-quality-class reference, but it is not competitive with the vLLM
AutoRound `65.276 tok/s` row. Do not spend more config-screen time here unless
there is a new source-level llama.cpp Qwen/GDN mechanism or a materially
different GGUF quant/backend.

P-min evidence:
`../../experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-07-05-pmin-screen-and-harness-fix.md`.

## Promotion Requirements

A row can be promoted here only if it passes the realistic final gate:

- fixed Qwen realistic suite;
- each prompt once as a cold response;
- no prompt/KV/context checkpoint/response reuse;
- no n-gram or history-accelerated result counted as fresh throughput;
- target model/quant unchanged;
- MTP accepted tokens are verified by the target model;
- primary metric is median generated-token throughput for tokens 1-100 after
  TTFT across the suite.

If llama.cpp does not expose `cached_tokens=0`, the packet must say so and must
include the launcher settings used to avoid context checkpoints and prompt
cache reuse.
