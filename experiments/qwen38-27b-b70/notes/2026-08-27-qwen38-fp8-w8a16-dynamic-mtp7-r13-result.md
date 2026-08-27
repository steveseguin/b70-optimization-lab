# Qwen3.8 FP8 dynamic MTP7 R13 positive screen

The preregistered MTP7-at-one/MTP1-at-load treatment passed every frozen gate
and is a positive screen pending an independent replication.

| Shape | promoted MTP5 median | MTP7 R13 | change |
| --- | ---: | ---: | ---: |
| one user, fresh after-TTFT decode | 128.428318 | **138.778590** | **+8.06%** |
| c64 aggregate decode | 1,098.315357 | **1,101.186445** | **+0.26%** |

The declared c64 row returned all 8,192 requested tokens with complete token
IDs, zero cached tokens, and zero cross-base oracle collisions. The same live
service passed c2 output isolation, 7/7 sequential exact cases, 8/8 repeat
stability, exact frozen-baseline agreement, and 512/512 synchronized
concurrent exact-answer requests.

The excluded c64 transition measured 1,029.775527 tok/s and is retained only
as conditioning evidence. The first eligible cache-zero single row is the
declared one-user result; repeated-prompt support rows are not averaged into
the headline.

After the final health check, both workers reported cleanup complete. The
five-second shutdown grace then expired and the already-idle EngineCore was
force-killed. There was no `EngineDeadError`, failed request, OOM kill, or
nonzero container exit. The shutdown receipt remains in the evidence.

This checkpoint contains one publisher MTP layer; MTP7 serially reuses it
seven times only for a singleton request. Two or more active requests use
MTP1. The service is limited to 256 tokens, and only c1 and c64 were measured.
Raw evidence is in
[`../data/qwen38-fp8-w8a16-mtp7-dynamic-mtp1-20260827-r13/`](../data/qwen38-fp8-w8a16-mtp7-dynamic-mtp1-20260827-r13/).
No missing depth, context, or concurrency is inferred, interpolated, or
extrapolated. Promotion requires the separately preregistered R14 replication.
