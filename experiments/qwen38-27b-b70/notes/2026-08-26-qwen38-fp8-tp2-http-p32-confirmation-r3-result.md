# Qwen3.8 official FP8 TP2 p32 HTTP confirmation R3 result

Status: **qualified output-audited HTTP concurrency profile**.

Two wholly new fresh servers reproduced the 32-active-slot profile. Both
attempts passed direct model verification, returned 128 raw token IDs for
every response, reported zero cached prompt tokens, produced no cross-base
compact-oracle collision, and tore down cleanly. The excluded R2 p32
observation is not part of these medians.

| Concurrent HTTP users | Aggregate tok/s | Per-user tok/s | TTFT p50 / p95 ms | Queued |
| ---: | ---: | ---: | ---: | :---: |
| 1 | 21.552291 | 21.552291 | 94.877 / 94.877 | no |
| 2 | 41.283248 | 20.641624 | 126.510 / 179.162 | no |
| 4 | 80.883699 | 20.220925 | 229.458 / 229.668 | no |
| 8 | 154.663420 | 19.332927 | 290.866 / 291.105 | no |
| 16 | 281.199884 | 17.574993 | 304.845 / 444.262 | no |
| 32 | **470.181647** | 14.693176 | 484.531 / 827.564 | no |
| 64 | 474.536615 | 7.414635 | 4,720.881 / 9,375.086 | yes |

c1-c32 are within the configured 32 active service slots. c64 includes queue
wait and is not evidence for 64 active users. Every throughput relative range
was below `0.251%`; the worst preregistered TTFT/end-to-end p50/p95 range was
`6.359%`. These pass the 10% throughput and 15% latency limits.

This is the same official FP8 revision, pinned vLLM image, TP2 topology, FP16
KV, target-only/MTP0 generation, 4,096-token capacity, 256 batched-token cap,
cache-off policy, and size-one graph route as preregistered. The only capacity
setting is `max_num_seqs=32`. Greedy token identity can vary with TP2 batch
shape, so the gate establishes complete isolated outputs rather than universal
sequential token identity.

The exact per-attempt receipts and the
[structured median](../data/2026-08-26-qwen38-fp8-tp2-http-p32-confirmation-r3-result.json)
are in this repository. No point is interpolated or extrapolated.
