# Future Research

- Long-context capacity once 2K decode is correct: 8K, 32K, then larger windows.
- OpenAI-compatible service profile after single-request throughput is stable.
- DeepSeek V4 MTP draft model support for verified speculative decoding.
- Port or replace TileLang sparse attention kernels for XPU if the vLLM backend
  remains CUDA-only.
- Investigate whether Intel XMX int4 kernels can directly accelerate DeepSeek
  V4's W4A16 dense and MoE matrices without dequantization.
- Compare AutoRound W4A16 against official NVFP4/GGUF alternatives only after
  workloads are matched.
- Prepare a reproducible `repro/` folder when a promoted result exists.
