# Qwen3.8 FP8 dynamic MTP3-at-one/MTP1-at-load R6 result

R6 passed every preregistered gate and is a positive screen pending an
independent fresh-server replication.

| Shape | promoted MTP2→MTP1 median | R6 MTP3→MTP1 | change |
| --- | ---: | ---: | ---: |
| one user, 40 prompt + 128 output | 83.680193 | **99.712488** | **+19.16%** |
| c64 aggregate, 8,192 output tokens | 1,085.038992 | **1,066.000395** | **−1.75%** |

The first eligible single row was cache-zero and cleared the frozen +2% gate.
The declared c64 run returned every requested token with complete IDs, zero
cached tokens, and zero cross-base collisions; it retained 98.25% of the
promoted aggregate median and cleared the frozen 98% floor. The excluded c64
transition measured 1,013.043780 tok/s and is not substituted for the declared
result.

Quality passed: c2 output isolation, 7/7 sequential exact cases, 8/8 repeat
stability, exact static-MTP2 baseline agreement, and 512/512 synchronized c64
exact-answer requests. The engine remained healthy and the container exited
zero.

The service still uses MTP1 at two or more active requests; only the singleton
depth changed from two to three serial applications of the checkpoint's one
publisher MTP layer. This is a 256-token service, not a 32K result. Raw
receipts live in
[`../data/qwen38-fp8-w8a16-mtp3-dynamic-mtp1-20260827-r6/`](../data/qwen38-fp8-w8a16-mtp3-dynamic-mtp1-20260827-r6/).
No value is interpolated or extrapolated.
