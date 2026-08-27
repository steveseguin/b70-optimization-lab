# Qwen3.8 FP8 dynamic MTP7 replication and promotion

The MTP7-at-one/MTP1-at-load service reproduced and passed every frozen
quality gate. It replaces MTP5-at-one as the selected short-context
interactive profile.

| Attempt | fresh single-user tok/s | c64 aggregate tok/s |
| --- | ---: | ---: |
| R13 | 138.778590 | 1,101.186445 |
| R14, new container and compile cache | 135.643836 | 1,103.345787 |
| two-attempt median | **137.211213** | **1,102.266116** |

Relative to the replicated MTP5-to-MTP1 profile, the new median improves
single-user decode by **6.84%** and aggregate c64 throughput by **0.36%**.
Both attempts returned all 8,192 declared c64 tokens with complete IDs, zero
cached tokens, and zero cross-base collisions.

Each attempt passed c2 output isolation, 7/7 sequential exact cases, 8/8
repeat stability, exact frozen-baseline comparison, and 512/512 synchronized
c64 exact-answer requests. Across the two attempts that is 1,024/1,024
concurrent exact answers.

After each final health check, both workers reported cleanup complete; vLLM's
five-second shutdown grace then expired and the already-idle EngineCore was
force-killed. Neither attempt logged `EngineDeadError`, failed a request, was
OOM-killed, or exited nonzero. Both receipts remain in the raw evidence.

The checkpoint contains one publisher MTP layer; MTP7 serially reuses it seven
times only for a singleton request. Two or more active requests use MTP1. This
is a 256-token service. Only c1 and c64 were measured; the guide does not fill
intermediate concurrency or long-context cells. Raw evidence is in
[`../data/qwen38-fp8-w8a16-mtp7-dynamic-mtp1-20260827-r13/`](../data/qwen38-fp8-w8a16-mtp7-dynamic-mtp1-20260827-r13/)
and
[`../data/qwen38-fp8-w8a16-mtp7-dynamic-mtp1-20260827-r14/`](../data/qwen38-fp8-w8a16-mtp7-dynamic-mtp1-20260827-r14/).
No value is interpolated or extrapolated.
