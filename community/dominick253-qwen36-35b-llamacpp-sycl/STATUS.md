# Qwen3.6 35B A3B Q8_0 on 2x Intel Arc Pro B70 (llama.cpp SYCL)

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | unreviewed |
| Verified on B70 | yes (2x B70, Ubuntu 26.04, xe driver) |
| Speed benchmarked | no |
| Quality gated | no |

## Summary

llama.cpp SYCL serving Qwen3.6-35B-A3B in Q8_0 quantization on 2x Intel Arc
Pro B70 with MTP speculative decoding, 512K context, reasoning enabled. Two
independent GPU endpoints (ports 8001/8002).

## Provenance

- Contributor: dominick253
- Model: Qwen/Qwen3.6-35B-A3B (Q8_0, Unsloth Dynamic 2.0 GGUF, 37GB)
- Runtime: llama.cpp fb92d8f18, IntelLLVM 2026.1.0, SYCL backend
- Build: build-intel/bin/llama-server
- GPU: 2x Intel Arc Pro B70 (Battlemage G31, 8086:e223)
- Host: Ubuntu 26.04 LTS, kernel 7.0.0-28-generic, xe driver, GuC 70.58.0
- CPU: AMD Ryzen 9 9950X (16C/32T), 60GB RAM
- Speculative decoding: draft-MTP2
- Context: 524288 tokens, Q8_0 KV cache
- Reasoning: enabled, 4096-token budget

## Known Limitations

- Not speed-benchmarked or quality-gated
- No tensor parallelism between GPUs (each serves full model independently)
- Q8_0 uses ~74GB total GPU memory (37GB per GPU)
- Not yet tested with realistic prompt suite per repo quality rules
