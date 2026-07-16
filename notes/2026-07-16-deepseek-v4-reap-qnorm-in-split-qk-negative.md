# DeepSeek V4 REAP QNorm-in-split-QK fusion negative

## Candidate

The frozen REAP K160 Q4 TP4+EP MTP1 lane currently submits WQ_B, fused QNorm/RoPE/KV insertion, split QK, and split PV as four device nodes. oneDNN cannot express the RMSNorm, RoPE, and paged-cache side effects as WQ_B post-ops, so the graph-neutral candidate was:

1. leave WQ_B unchanged;
2. make the fused producer KV-only;
3. move Q RMSNorm and RoPE into the existing split-QK register prologue;
4. leave PV unchanged.

This preserved model, Q4 weights, FP8 KV format, TP4+EP topology, MTP1 depth, exact target verification, and graph node count.

## Reproduction identity

- vLLM base: `cfa2a67b4b`
- candidate commit: `a8897ad76`
- candidate restoration/revert: `e53285daf`
- benchmark: `experiments/deepseek-v4-flash-reap-xpu-b70/scripts/bench-qnorm-in-split-qk.py`
- raw data: `data/deepseek-v4-reap-qnorm-in-split-qk-20260716/`
- shape: M=2, 64 heads, compressed width 256, SWA width/length 128, split geometry 4/16/8

The benchmark measures the complete KV producer + QK + PV chain. It includes the same raw-Q copy in both branches, uses valid synthetic UE8M0/BF16 caches, and varies raw Q/KV values. It checks paged cache bytes, materialized QK scores, LSE, and final attention output at bitwise tolerance.

## Results

| GPU | compressed length | exact changing cases | baseline (ms) | candidate (ms) | projected delta over 43 layers (ms) |
|---|---:|---:|---:|---:|---:|
| 0 | 4 | 8 | 0.121732 | 0.116948 | +0.205712 |
| 1 | 32 | 8 | 0.131664 | 0.126568 | +0.219128 |
| 2 | 128 | 8 | 0.189228 | 0.187668 | +0.067080 |
| 3 | 256 | 8 | 0.265928 | 0.269048 | -0.134160 |

All 32 changing cases were bitwise exact. The candidate nevertheless failed the required 0.50 ms/43-layer performance gate on every tested sparse length and regressed at length 256.

## Interpretation and decision

The Q workgroups in the existing producer are mostly hidden by the KV workgroup and available XPU parallelism. Moving that arithmetic into QK removes a BF16 store/read but lengthens the consumer kernel, so the complete-chain benefit is small and disappears as sparse QK work grows.

Reject the candidate and do not integrate it into service or graph replay. The implementation remains preserved at `a8897ad76`; active source was restored by `e53285daf`. This also closes the broader M=2 attention/QNorm specialization lane together with the paired M=1/M=2 attention result: neither boundary has enough measured complete-cycle ceiling to move the 60.264242 tok/s record materially.
