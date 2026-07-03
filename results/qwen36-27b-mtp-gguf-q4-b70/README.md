# Qwen3.6 27B MTP GGUF Q4 on B70

This result packet is reserved for the Unsloth Qwen3.6 27B MTP GGUF Q4 lane on
Intel Arc Pro B70.

## Status

Bring-up is in progress. No promoted strict fresh-response result exists yet.

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
