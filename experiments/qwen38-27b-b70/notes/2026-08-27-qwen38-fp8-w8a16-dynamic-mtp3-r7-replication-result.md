# Qwen3.8 FP8 dynamic MTP3 replication and promotion

The MTP3-at-one/MTP1-at-load service reproduced and passed every frozen
quality gate. It replaces MTP2-at-one as the selected short-context
interactive profile.

| Attempt | fresh single-user tok/s | c64 aggregate tok/s |
| --- | ---: | ---: |
| R6 | 99.712488 | 1,066.000395 |
| R7, new container and compile cache | 100.148379 | 1,083.879484 |
| two-attempt median | **99.930434** | **1,074.939939** |

Relative to the replicated MTP2-to-MTP1 profile, the new median improves
single-user decode by **19.42%** while retaining **99.07%** of aggregate c64
throughput. Both attempts returned all 8,192 declared c64 tokens with complete
IDs, zero cached tokens, and zero cross-base collisions.

Each attempt passed c2 output isolation, 7/7 sequential exact cases, 8/8
repeat stability, exact frozen-baseline comparison, and 512/512 synchronized
c64 exact-answer requests. Across the two attempts that is 1,024/1,024
concurrent exact answers.

R7's post-gate `docker stop` reached vLLM's five-second worker grace timeout
and logged a shutdown-only `EngineDeadError` while forcing the already-idle
EngineCore. The health check immediately before stop passed, no request failed,
the workers had reported cleanup, and the container exited zero. This is
preserved as shutdown evidence rather than hidden or treated as an inference
failure.

The checkpoint still contains one publisher MTP layer; MTP3 serially reuses it
three times only for a singleton request. Two or more active requests use
MTP1. This is a 256-token service. Only c1 and c64 were measured; the guide
does not fill intermediate concurrency or long-context cells. Raw evidence is
in
[`../data/qwen38-fp8-w8a16-mtp3-dynamic-mtp1-20260827-r6/`](../data/qwen38-fp8-w8a16-mtp3-dynamic-mtp1-20260827-r6/)
and
[`../data/qwen38-fp8-w8a16-mtp3-dynamic-mtp1-20260827-r7/`](../data/qwen38-fp8-w8a16-mtp3-dynamic-mtp1-20260827-r7/).
No value is interpolated or extrapolated.
