# Qwen3.8 FP8 dynamic MTP8 R15 positive screen

The preregistered MTP8-at-one/MTP1-at-load treatment passed every frozen gate
and is a positive screen pending independent replication.

| Shape | promoted MTP7 median | MTP8 R15 | change |
| --- | ---: | ---: | ---: |
| one user, fresh after-TTFT decode | 137.211213 | **146.808244** | **+6.99%** |
| c64 aggregate decode | 1,102.266116 | **1,095.553649** | **-0.61%** |

The declared c64 row returned all 8,192 tokens with complete IDs, cache zero,
and no cross-base collisions. The service also passed c2 isolation, 7/7 exact
sequential cases, 8/8 repeat stability, frozen-baseline agreement, and 512/512
synchronized exact-answer requests. The excluded transition is preserved but
not used. Shutdown was healthy: workers cleaned up, the idle EngineCore was
force-killed after the five-second grace period, and the container exited zero
without OOM or `EngineDeadError`.

Raw evidence is in
[`../data/qwen38-fp8-w8a16-mtp8-dynamic-mtp1-20260827-r15/`](../data/qwen38-fp8-w8a16-mtp8-dynamic-mtp1-20260827-r15/).
Nothing is promoted until R16 passes; no missing shape is extrapolated.
