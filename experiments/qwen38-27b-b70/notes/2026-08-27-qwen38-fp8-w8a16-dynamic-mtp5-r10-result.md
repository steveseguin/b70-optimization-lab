# Qwen3.8 FP8 dynamic MTP5 R10 positive screen

The preregistered MTP5-at-one/MTP1-at-load treatment passed every gate and is
a positive screen pending an independent replication.

| Shape | promoted MTP4 median | MTP5 R10 | change |
| --- | ---: | ---: | ---: |
| one user, fresh after-TTFT decode | 116.711347 | **128.579263** | **+10.17%** |
| c64 aggregate decode | 1,091.652182 | **1,095.783748** | **+0.38%** |

The c64 row returned all 8,192 declared tokens with complete token IDs, zero
cached tokens, and zero cross-base oracle collisions. The same live service
passed c2 output isolation, 7/7 sequential exact cases, 8/8 repeat stability,
exact frozen-baseline agreement, and 512/512 synchronized concurrent
exact-answer requests.

The excluded transition measured 1,025.298527 tok/s and is preserved but not
used. The first eligible cache-zero single row is the declared one-user
result. No repeated-prompt mean is promoted.

After the final health check, both workers reported cleanup complete. The
five-second vLLM shutdown grace nevertheless expired and the already-idle
EngineCore was force-killed. There was no `EngineDeadError`, no request failed,
the container was not OOM-killed, and it exited zero. The shutdown receipt is
preserved rather than silently discarded.

This checkpoint still supplies one MTP layer; MTP5 serially reuses it five
times only for one active request. Two or more active requests use MTP1. The
service is limited to 256 tokens, and only c1 and c64 were measured. Raw
evidence is in
[`../data/qwen38-fp8-w8a16-mtp5-dynamic-mtp1-20260827-r10/`](../data/qwen38-fp8-w8a16-mtp5-dynamic-mtp1-20260827-r10/).
No missing depth, context, or concurrency is inferred, interpolated, or
extrapolated.
