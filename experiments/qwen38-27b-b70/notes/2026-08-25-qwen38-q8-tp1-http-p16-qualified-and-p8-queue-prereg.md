# Qwen3.8 Q8_0 TP1: p16 qualified baseline and p8 queued follow-up

The preregistered two-fresh-server p16 publication gate passed. Every request
returned 128 complete raw token IDs with prompt caching disabled, and no output
matched the frozen sequential oracle for another base task. Greedy output
remained batch-shape-dependent, so the classification is output-isolation
qualified rather than sequentially identical.

| simultaneous HTTP users | median aggregate tok/s | per-user tok/s | relative range |
| ---: | ---: | ---: | ---: |
| 1 | 17.839 | 17.839 | 0.42% |
| 2 | 29.110 | 14.555 | 1.43% |
| 4 | 46.775 | 11.694 | 0.30% |
| 8 | 66.330 | 8.291 | 0.88% |
| 16 | 43.603 | 2.725 | 0.63% |

All markers are medians of two exact fresh-server attempts. No point is
interpolated or extrapolated. The 64-slot/32K and 32-slot/16K profiles were
both retained device-memory failures; the largest measured F16-KV allocation
fit is 16 slots at 8K total context.

The 34.26% aggregate drop from 8 to 16 users is a clear scheduler/batch-shape
weak spot. The sealed r4 follow-up keeps eight active slots and 4K total
context while admitting 1–64 simultaneous HTTP requests to the server queue.
Its pilot rates are excluded; if output gates pass, compact 64-row digests and
two new publication attempts are required.
