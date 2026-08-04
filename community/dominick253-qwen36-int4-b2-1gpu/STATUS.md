# STATUS — Qwen3.6 27B / 35B A3B INT4 (vLLM Docker, b2, one GPU)

## Current State

**PENDING BENCHMARK** — Smoke tests pass (text, thinking, tool calls, vision,
MTP ~85-88% acceptance). Full benchmark not yet run. Benchmark coming.

## Environment

- 2x Intel Arc B70 (Battlemage G31), 32 GB each
- AMD Ryzen 9 9950X
- Ubuntu 26.04 LTS, kernel 7.0.0-29-generic
- vLLM 0.21 via `intel/llm-scaler-vllm:0.21.0-b2`

## Launch Script

- `vllm-qwen36-int4-b2-1gpu.sh` — full launcher with health check + smoke tests
- One model per GPU: 27B on GPU 0 (port 8001), 35B on GPU 1 (port 8002)
- INT4 in-place quant (`sym_int4`) via `VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1`
- FP8 KV cache (`fp8_e4m3`) via Triton attention backend
- MTP speculative decoding (`qwen3_5_mtp`, 2 tokens)
- Thinking mode ON + preserved, reasoning parser qwen3
- Tool calling: `--enable-auto-tool-choice --tool-call-parser qwen3_xml`
- Vision enabled and verified

## Measured (smoke-level, 2026-08-04)

| Model | GPU | Weights | KV cache | KV tokens |
| --- | --- | --- | --- | --- |
| Qwen3.6-27B | 0 | 18.2 GiB | 10.2 GiB | 292,759 |
| Qwen3.6-35B-A3B MoE | 1 | 19.7 GiB | 8.74 GiB | 728,975 |

## Known Issues

- TP=2 is unusable on b2/B70: multi-GPU all-reduce returns NaN on prefill-sized
  buffers (Intel's own source comment); TP=1 required
- Eager mode enabled (`--enforce-eager`) — may impact perf vs XPU graph
- `min_p`/`logit_bias` ignored under speculative decoding (vLLM warning)

## Next Steps

- Run full benchmark suite (throughput, TTFT, thinking vs non-thinking, MTP
  acceptance, fp8-KV vs fp16-KV comparison)
- Update README.md with benchmark results
- Submit to LocalMaxxing if results beat current baseline
