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
- median `30.679 tok/s` for generated tokens 1-100 after TTFT, p10 `27.589`,
  mean `30.405`, full-output median `29.860`, TTFT median `499.8 ms`;
- evidence:
  `../../data/qwen36-27b-mtp-gguf-q4-b70-baselines/llamacpp-mtp3-aot-np1-realistic128-20260703T060748Z.json`;
- compact sweep ledger:
  `initial-realistic-sweep-20260703.json`.
- LocalMaxxing reference:
  `cmr6mn5ct0076mn01on3dnpyn`, submitted as a valid but non-competitive
  model/runtime variation; queue and response are
  `../../experiments/qwen36-27b-mtp-gguf-q4-b70/localmaxxing/qwen36-27b-gguf-q4-mtp3-20260703.queue.json`
  and
  `../../data/localmaxxing-responses/qwen36-27b-gguf-q4-mtp3-20260703.submit.log`.

The current valid INT4/Q4 Qwen27 headline remains the separate
`Intel/Qwen3.6-27B-int4-AutoRound` vLLM/XPU lane at median `53.522 tok/s` on
the fixed Qwen realistic suite:

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
