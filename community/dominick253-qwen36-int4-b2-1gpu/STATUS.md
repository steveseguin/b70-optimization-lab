# STATUS — Qwen3.6 27B / 35B A3B INT4 (vLLM Docker, b2, one GPU)

## Current State

**BENCHMARKED** — llama-benchy results recorded (2026-08-04). Full tables in
`benchmarks/BENCHMARKS.md`; raw per-run JSON/CSV in `benchmarks/`.

## Environment

- 2x Intel Arc B70 (Battlemage G31), 32 GB each
- AMD Ryzen 9 9950X
- Ubuntu 26.04 LTS, kernel 7.0.0-29-generic
- vLLM 0.21 via `intel/llm-scaler-vllm:0.21.0-b2`

## Launch Script

- `vllm-qwen36-int4-b2-1gpu.sh` — full launcher with health check + smoke tests
- One model per GPU: 27B on GPU 0 (port 8001), 35B on GPU 1 (port 8002)
- **FINAL config (2026-08-05):** 27B = 131k ctx / 2 seqs / temp 0.6 / presence 0.0;
  35B = 262k ctx / 3 seqs / temp 1.0 / presence 1.5
- INT4 in-place quant (`sym_int4`) via `VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1`
- FP8 KV cache (`fp8_e4m3`) via Triton attention backend
- **MTP disabled** (A/B-verified deep-context penalty; see benchmarks/)
- Thinking mode ON + preserved, reasoning parser qwen3
- Tool calling: `--enable-auto-tool-choice --tool-call-parser qwen3_xml`
- Vision enabled and verified

## Benchmarks (llama-benchy 0.4.1.dev1, pp=2048 tg=1024, 5 runs/depth)

| Model | depth | pp tok/s | tg tok/s | peak tok/s | TTFR ms |
| --- | --- | --- | --- | --- | --- |
| Qwen3.6-35B-A3B MoE (GPU 1) | 0 | 5647.8 | 103.3 | 119.4 | 378.3 |
| Qwen3.6-35B-A3B MoE (GPU 1) | 4096 | 6220.4 | 77.8 | 89.4 | 946.6 |
| Qwen3.6-35B-A3B MoE (GPU 1) | 8192 | 5671.5 | 33.3 | 43.4 | 1691.0 |
| Qwen3.6-35B-A3B MoE (GPU 1) | 16384 | 5573.9 | 39.7 | 52.8 | 3021.2 |
| Qwen3.6-35B-A3B MoE (GPU 1) | 32768 | 4677.6 | 24.8 | 33.4 | 6814.8 |
| Qwen3.6-27B (GPU 0) | 0 | 1494.6 | 46.3 | 54.8 | 1307.1 |
| Qwen3.6-27B (GPU 0) | 4096 | 1536.1 | 35.9 | 44.4 | 3711.1 |
| Qwen3.6-27B (GPU 0) | 8192 | 1506.8 | 29.0 | 37.4 | 6211.4 |
| Qwen3.6-27B (GPU 0) | 16384 | 1421.5 | 21.6 | 28.8 | 11781.5 |
| Qwen3.6-27B (GPU 0) | 32768 | 1264.3 | 14.9 | 19.2 | 25060.4 |

Method + verification + reproduction in `benchmarks/BENCHMARKS.md`.

## Measured (smoke-level, 2026-08-04)

| Model | GPU | Weights | KV cache | KV tokens |
| --- | --- | --- | --- | --- |
| Qwen3.6-27B | 0 | 18.2 GiB | 10.2 GiB | 292,759 |
| Qwen3.6-35B-A3B MoE | 1 | 19.7 GiB | 8.74 GiB | 728,975 |

## Known Issues

- TP=2 is unusable on b2/B70: multi-GPU all-reduce returns NaN on prefill-sized
  buffers (Intel's own source comment); TP=1 required
- **MTP degrades deep-context decode** (A/B verified 2026-08-05): at depth 32k,
  MTP costs 3.45x (35B MoE) / 1.56x (27B) decode throughput — draft+verify both
  attend the full KV cache. Disabled by default in the final config.
- **35B MoE + thinking emits `!`-repetition garbage (open)**: reproduced across
  all sampling values; 27B dense clean on identical recipe. Workaround: thinking
  OFF on 35B or different quantization. Details in benchmarks/BENCHMARKS.md.
- Eager mode enabled (`--enforce-eager`) — may impact perf vs XPU graph
- `min_p`/`logit_bias` ignored under speculative decoding (vLLM warning)

## Next Steps

- Submit to LocalMaxxing if results beat current baseline
- Optional: XPU-graph mode benchmark once stability permits
