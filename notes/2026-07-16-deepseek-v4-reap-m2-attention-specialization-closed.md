# DeepSeek V4 REAP M=2 attention specialization closed

## Objective and identity

Test whether the frozen DeepSeek V4 Flash REAP K160 Q4 TP4+EP MTP1 lane has a worthwhile verifier-specific attention fusion opportunity. This did not change the checkpoint, quantization, topology, speculative depth, or exact target verification.

- vLLM source: `/home/steve/src/deepseek-v4-vllm-clean` at `cfa2a67b4b`
- kernel: `split_fp8_sparse_attention`
- attention shape: 64 heads, compressed width/length 256/128, SWA width/length 128/128
- promoted geometry: `block_h=4`, `qk_warps=16`, `pv_warps=8`
- timing: 200 ms warmup, 1000 ms repetition window
- raw data: `data/deepseek-v4-reap-m2-attention-paired-20260716/`

The benchmark was extended with explicit M=1/M=2 rows, identical/shifted/disjoint index families, a fixed-geometry mode, and structured output. The final gate paired M=1 and M=2 sequentially on each physical B70 to remove card-to-card bias.

## Result

| GPU | M=1 median (us) | M=2 identical (us) | M=2 shifted (us) |
|---|---:|---:|---:|
| 0 | 177.840 | 178.672 | 178.308 |
| 1 | 177.476 | 179.036 | 178.360 |
| 2 | 177.476 | 178.724 | 178.308 |
| 3 | 177.372 | 178.984 | 178.256 |
| mean | 177.541 | 178.854 | 178.308 |

The mean M=2 increment was 1.313 us/layer for identical indices and 0.767 us/layer for shifted indices. Projected over 43 layers, that is only 0.0565 ms and 0.0330 ms per target-verification cycle respectively.

## Decision

Close the M=2 attention-specialization lane. The existing kernel already parallelizes the two verifier rows so effectively that there is less than 0.1 ms/cycle of measured M=2-specific overhead to recover. A bespoke cache-reuse kernel would be substantial work for an immaterial ceiling and could easily regress the already-good launch geometry.

This result does not claim that all attention time is free or that M=1 attention cannot ever improve. It specifically rules out treating the second verifier row as a large MTP1-cycle cost. The next work should remain on graph-node-removing fusion boundaries with a measured complete-cycle ceiling, especially the grouped M=2 MoE epilogue/reduction and graph-neutral integration of the exact QNorm/RoPE/FP8-KV kernel.
