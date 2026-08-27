# Qwen3.8 FP8 dynamic MTP8 replication and promotion

The MTP8-at-one/MTP1-at-load service reproduced and passed every frozen
quality gate. It replaces MTP7-at-one as the selected short-context
interactive profile.

| Attempt | fresh single-user tok/s | c64 aggregate tok/s |
| --- | ---: | ---: |
| R15 | 146.808244 | 1,095.553649 |
| R16, new container and compile cache | 146.820592 | 1,093.075885 |
| two-attempt median | **146.814418** | **1,094.314767** |

Relative to the replicated MTP7-to-MTP1 profile, the new median improves
single-user decode by **7.00%** while retaining **99.28%** of c64 aggregate
throughput. Both attempts returned all 8,192 declared c64 tokens with complete
IDs, zero cached tokens, and zero cross-base collisions.

Each attempt passed c2 output isolation, 7/7 sequential exact cases, 8/8
repeat stability, exact frozen-baseline comparison, and 512/512 synchronized
c64 exact-answer requests. Across the two attempts that is 1,024/1,024
concurrent exact answers.

After each final health check, both workers reported cleanup complete; vLLM's
five-second shutdown grace then expired and the already-idle EngineCore was
force-killed. Neither attempt logged `EngineDeadError`, failed a request, was
OOM-killed, or exited nonzero. Both receipts remain in the raw evidence.

The checkpoint contains one publisher MTP layer; MTP8 serially reuses it eight
times only for a singleton request. Two or more active requests use MTP1. This
is a 256-token service. Only c1 and c64 were measured; the guide does not fill
intermediate concurrency or long-context cells. Raw evidence is in
[`../data/qwen38-fp8-w8a16-mtp8-dynamic-mtp1-20260827-r15/`](../data/qwen38-fp8-w8a16-mtp8-dynamic-mtp1-20260827-r15/)
and
[`../data/qwen38-fp8-w8a16-mtp8-dynamic-mtp1-20260827-r16/`](../data/qwen38-fp8-w8a16-mtp8-dynamic-mtp1-20260827-r16/).
No value is interpolated or extrapolated.
