# Qwen3.8 27B Q4_K_M + Q4_0 MTP2 TP1 HTTP concurrency

Status: **qualified at 16 slots / 8K total context**.

The selected profile is the first viable cell in the preregistered capacity
descent. The server failed before any request at 64 slots/32K, 64 slots/16K,
and 32 slots/16K with `UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY`. It initialized
at 16 slots/8K (512 nominal context tokens per slot).

| Concurrent users | Aggregate tok/s | Per-user tok/s | Fresh attempts | Relative range |
| ---: | ---: | ---: | --- | ---: |
| 1 | 34.893 | 34.893 | 35.269 / 34.516 | 2.16% |
| 2 | 41.255 | 20.627 | 41.880 / 40.629 | 3.03% |
| 4 | 52.355 | 13.089 | 53.086 / 51.624 | 2.79% |
| 8 | 47.914 | 5.989 | 48.296 / 47.532 | 1.60% |
| 16 | **68.341** | 4.271 | 68.965 / 67.717 | 1.83% |

Both fresh servers returned exactly 128 uncached token IDs for every
throughput request, with zero cross-base oracle collisions. Greedy tokens are
batch-shape-dependent at multi-user shapes, so the curve is classified as
output-isolation-qualified rather than sequential-token-identical. A separate
16-way exact-answer canary ran eight rounds per attempt: **256/256 passed**,
with zero cached tokens.

The structured authority is
[`2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-http-concurrency-r2-result.json`](../data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-http-concurrency-r2-result.json).
Every point is measured; none is interpolated or extrapolated. The result is
specific to 8K total configured context and is not a 32K-per-user result.
