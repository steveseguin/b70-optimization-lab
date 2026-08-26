# Qwen3.8 official FP8 TP2 exact HTTP depth R1

The preregistered 33,024-token target-only/MTP0 service profile passed all six
exact active-context cells on two Arc Pro B70 cards. The model, image, FP16 KV,
TP2 topology, size-one PIECEWISE graph, cache policy, fixture, sampler, and
128-token output shape stayed fixed.

| Exact prompt tokens | Decode tok/s | TTFT ms | Effective prompt proxy tok/s |
| ---: | ---: | ---: | ---: |
| 2,048 | 21.835160 | 1,385.137 | 1,478.554 |
| 4,096 | 21.673278 | 2,605.858 | 1,571.843 |
| 8,192 | 21.270146 | 5,191.968 | 1,577.822 |
| 16,384 | 20.927452 | 10,533.231 | 1,555.458 |
| 24,576 | 20.650133 | 16,139.140 | 1,522.758 |
| 32,768 | 20.389854 | 21,872.674 | 1,498.125 |

Every request reported the exact prompt count, zero cached tokens, and 128
streamed output token IDs, with no truncation or context shift. The container
cleaned up without a survivor or open port. The fixture is grade-C repeated
token shape evidence, not natural prose. Every point is measured; none is
interpolated or extrapolated.

The effective prompt-throughput proxy is `exact prompt tokens / measured HTTP
TTFT seconds`. It includes HTTP scheduling, chunked prefill, and first-token
work, so it must not be relabeled as a server-only or kernel-only prefill rate.

Evidence: [`summary.json`](../data/qwen38-fp8-tp2-http-depth-20260826-r1-attempt1/summary.json).
The preregistration remains at
[`2026-08-26-qwen38-fp8-tp2-http-depth-r1-prereg.json`](../data/2026-08-26-qwen38-fp8-tp2-http-depth-r1-prereg.json).
