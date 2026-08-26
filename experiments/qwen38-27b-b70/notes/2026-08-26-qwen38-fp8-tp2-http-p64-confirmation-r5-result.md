# Qwen3.8 official FP8 TP2 p64 HTTP confirmation R5 result

Status: **qualified output-audited HTTP concurrency profile**.

Two wholly new fresh servers reproduced the 64-active-slot profile. Both
attempts passed direct model verification, complete-output, cache-zero,
cross-base compact-oracle isolation, and clean teardown gates. The R4
diagnostic is excluded from these medians.

| Concurrent HTTP users | Aggregate tok/s | Per-user tok/s | TTFT p50 / p95 ms |
| ---: | ---: | ---: | ---: |
| 1 | 21.554729 | 21.554729 | 96.669 / 96.669 |
| 2 | 41.371500 | 20.685750 | 125.962 / 178.579 |
| 4 | 80.966535 | 20.241634 | 232.083 / 232.298 |
| 8 | 155.050071 | 19.381259 | 294.478 / 295.145 |
| 16 | 280.827699 | 17.551731 | 310.737 / 449.855 |
| 32 | 469.849149 | 14.682786 | 495.173 / 837.908 |
| 64 | **695.792088** | 10.871751 | 889.839 / 1,744.033 |

All points are within the configured 64 active service slots. The worst
throughput relative range was `0.261%`; the worst TTFT/end-to-end p50/p95
range was `9.423%`. These pass the preregistered 10% throughput and 15%
latency limits.

The profile uses the same official FP8 revision, pinned vLLM image, TP2,
FP16 KV, target-only/MTP0 generation, 4,096-token capacity, 256 batched-token
limit, cache-off policy, and size-one graph route as the earlier qualified
profiles. Only `max_num_seqs=64` identifies this capacity setting. Greedy token
identity can vary with TP2 batch shape, so the gate establishes complete
isolated outputs rather than universal sequential identity.

The exact receipts and [structured median](../data/2026-08-26-qwen38-fp8-tp2-http-p64-confirmation-r5-result.json)
are in this repository. No point is interpolated or extrapolated.
