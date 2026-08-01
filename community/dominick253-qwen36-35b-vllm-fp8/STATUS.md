# STATUS — Qwen3.6 35B A3B FP8 (vLLM Docker)

## Current State

**PENDING BENCHMARK** — Smoke tests pass. Full benchmark not yet run.

## Environment

- 2x Intel Arc B70 (Battlemage G31), 32 GB each
- AMD Ryzen 9 9950X
- Ubuntu 26.04 LTS, kernel 7.0.0-28-generic
- vLLM 0.21 via `intel/llm-scaler-vllm:0.21.0-b1`

## Launch Script

- `vllm-qwen36-35b-fp8.sh` — full launcher with health check + smoke tests
- Port: 8001 | TP: 2 | Context: 262144 | Max seqs: 4
- FP8 in-place quant via `VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1`
- Thinking mode ON via chat template kwargs + reasoning parser qwen3

## Known Issues

- Eager mode enabled (EAGER=1) — may impact perf vs CUDA graph warmup
- Benchmark TBD

## Next Steps

- Run full benchmark suite (throughput, TTFT, thinking vs non-thinking, etc.)
- Update README.md with benchmark results
- Submit to LocalMaxxing if results beat current baseline
