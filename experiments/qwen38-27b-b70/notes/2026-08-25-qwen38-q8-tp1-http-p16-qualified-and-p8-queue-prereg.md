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

## R5 publication result

R5 passed both fresh-server attempts and every output/stability gate. The
qualified queued-p8 aggregate curve is:

| simultaneous HTTP requests | median aggregate tok/s | relative range |
| ---: | ---: | ---: |
| 1 | 18.071 | 0.15% |
| 2 | 29.148 | 0.06% |
| 4 | 47.518 | 0.95% |
| 8 | 67.073 | 0.53% |
| 16 | 68.128 | 0.20% |
| 32 | 68.311 | 0.14% |
| 64 | **68.556** | 0.22% |

At 16 simultaneous requests, queued p8 improves over preallocated p16 by
**56.24%** (`68.128 / 43.603 - 1`). Aggregate remains essentially flat from
16 through 64 requests. The tradeoff is queueing latency: this campaign
qualifies aggregate batch-wall throughput, not TTFT or per-request latency.
