# Qwen3.8 GPTQ quality, KV, and runtime-dtype decision

Date: 2026-08-16. Hardware: one ASRock Arc Pro B70 for the GPTQ/vLLM rows;
two ASRock Arc Pro B70s for the GGUF controls. All requests disabled thinking
and used greedy decoding.

## Decision

The GPTQ INT4/MTP lane is retained as useful experimental performance work,
but it is **not the repository's quality-default Qwen3.8 deployment**. The
exact GPTQ checkpoint failed a simple deterministic Python-result canary that
both Q8_0 and Q4_K_M answered correctly. Native MTP and FP8 KV introduced no
additional observed drift relative to that GPTQ target, but target-verifier
parity cannot recover information already lost in the target checkpoint.

The primary quality-conservative service is therefore
[`repro/qwen38-27b-q8-tp2-asrock-b70`](../../../repro/qwen38-27b-q8-tp2-asrock-b70/README.md).
Q4_K_M remains a faster, explicitly lower-precision lane whose small semantic
gate also passed; it is not asserted to be universally equivalent to Q8.

## Performance and KV A/B

All rows used the exact pinned model/image, XPU graphs, 8K maximum context,
prefix cache off, scheduler budget 8192, p512/g128, five measured requests,
and client post-first decode accounting.

| Mode | KV | Median tok/s | Draft acceptance |
| --- | --- | ---: | ---: |
| target only | FP8 | `33.690260` | n/a |
| target only | native FP16 (`auto`) | **`34.160467`** | n/a |
| MTP4 | FP8 | `83.697153` | 510/544 (`93.75%`) |
| MTP4 | native FP16 (`auto`) | **`87.605425`** | 511/540 (`94.63%`) |

At this 8K service size, native FP16 KV was both faster and sufficient:
vLLM reported 93,262 tokens of cache capacity, versus 140,174 with FP8 KV.
Use `KV_CACHE_DTYPE=auto` for this experimental 8K lane. FP8 remains a
separate compressed-KV identity for longer-context capacity studies.

## Semantic gate

The model-specific suite checked exact copying, arithmetic, JSON schema,
factual recall, logic, a Python expression result, deterministic repeat
stability, and a needle recovered from an actual 3,829-token prompt.

| Route | Gate | Python canary | Needle | Relative parity |
| --- | --- | ---: | --- | --- |
| Q8_0 TP2, F16 KV, target only | pass | `14` | pass | quality oracle |
| Q4_K_M TP2, F16 KV, target only | pass | `14` | pass | same canary outputs as Q8 |
| GPTQ target, native FP16 KV | **fail** | `30` | pass | baseline |
| GPTQ MTP4, native FP16 KV | **fail** | `30` | pass | exact match to GPTQ target |
| GPTQ MTP4, FP8 KV | **fail** | `30` | pass | exact match to GPTQ target |

The failing prompt asks for the value of
`sum(i * i for i in range(4))`; the correct result is `14`. This is a bounded
canary, not a full benchmark suite, but one reproducible semantic failure is
enough to reject the checkpoint as a no-quality-loss default.

## Loaded MTP precision

The safetensors artifact contains 15 BF16 `mtp.*` tensors, but a fail-closed
probe of the exact pinned vLLM image showed every owned MTP parameter loaded as
`torch.float16`, including `model.fc`, the MTP attention projections, MLP
projections, and norms. The accurate description is therefore:

- artifact MTP tensors: BF16 on disk;
- runtime MTP parameters/compute dtype: FP16 under `--dtype float16`.

The logging-only probe is
[`tools/inspect_mtp_runtime_dtype.py`](../tools/inspect_mtp_runtime_dtype.py).

## Shutdown safety finding

The dtype message appeared before the vLLM server reached `/health`. Stopping
the container during subsequent graph/compiler initialization produced a Xe
CCS memory CAT error, engine reset, and timed-out `VLLM::EngineCor` job on
`0000:03:00.0`. The host remained responsive and both cards subsequently
returned to `Device State: normal` at idle clocks.

This does not establish that the dtype probe caused bad arithmetic. It does
establish an operational hazard: **do not stop this image during engine/graph
initialization merely because an inspection log line has appeared.** Wait for
`/health`, then stop with a grace period. The preserved kernel-window SHA is
listed below; the devcoredump was not consumed or deleted.

## Raw evidence identities

Raw files remain outside Git under
`/mnt/fast-ai/bench-results/qwen38-gptq-quality-20260816/`.
The machine-readable digest is
[`2026-08-16-quality-kv-dtype-summary.json`](2026-08-16-quality-kv-dtype-summary.json).

- FP16-KV target speed JSON: `1e28b30bef53f801287a7e8139451ddbee15d5a67a20be89833d4b1f2391a227`
- FP16-KV MTP4 speed JSON: `a1696b6dbd28ef31d2d085eddc29310d2834440aa8c83b89ea714ede3dd7849c`
- FP16-KV target quality: `b5e42c6e9963b55f2fbaede73cf54edcb9fc261ca63de2f87bcb9f50427b85c7`
- FP16-KV MTP4 quality: `cce0308274313232a5e911141dcce0eb806b89f2ac57d31c150b03f6e05ffead`
- FP8-KV MTP4 quality: `2779023f17a4f4b00517eea11fb1a1597b0ea90298129beedf0592c97dc562ce`
- Q8 TP2 quality: `60f82f0ce1cb54976577b75fe4daf04535af2a97ccd29484141aa1b303a6b1dc`
- Q4_K_M TP2 quality: `23e60ea5f0e2036ac050123e71acb459a845263f3e8525b62fce2e5d10a6d564`
- runtime-dtype log: `a6dfb75c52c008d5fd3cc61eefe25e898defd6c73c2c91e2635f5f6a17a7a092`
- shutdown/reset kernel window: `ecb4550343853580390e8f30ed16a9de18dfaf6b0f18da0e1476cd41afcaaac9`
