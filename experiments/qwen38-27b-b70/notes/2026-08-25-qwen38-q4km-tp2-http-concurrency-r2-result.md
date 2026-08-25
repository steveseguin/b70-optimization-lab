# Qwen3.8 Q4_K_M TP2 output-audited HTTP concurrency R2 result

Status: **qualified for output-audited aggregate service capacity**.

Two new 64-slot servers independently measured 1/2/4/8/16/32/64 synchronized
native HTTP requests. Every response returned all 128 raw token IDs, reported
zero cached prompt tokens, and avoided every frozen oracle belonging to a
different base task. Both attempts passed the preregistered output-isolation
gate. Sequential greedy identity varied with batch shape and is disclosed; it
is not claimed as batch invariant.

| concurrent users | attempt 1 tok/s | attempt 2 tok/s | published median tok/s | per user tok/s | relative range |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 42.327726 | 43.060745 | 42.694236 | 42.694236 | 1.717% |
| 2 | 61.752037 | 62.017292 | 61.884664 | 30.942332 | 0.429% |
| 4 | 87.927396 | 87.205414 | 87.566405 | 21.891601 | 0.824% |
| 8 | 108.565695 | 108.177446 | 108.371571 | 13.546446 | 0.358% |
| 16 | 109.199372 | 109.093734 | 109.146553 | 6.821660 | 0.097% |
| 32 | 127.426082 | 127.573520 | 127.499801 | 3.984369 | 0.116% |
| 64 | 165.656613 | 165.117959 | 165.387286 | 2.584176 | 0.326% |

The maximum relative range was `1.717%`, comfortably inside the frozen 10%
gate. The non-publishable oracle pilot is not included in any median. No point
is interpolated or extrapolated.

The complete raw attempts are retained under
[`attempt1`](../data/qwen38-q4km-tp2-http-concurrency-20260825-r2-attempt1/)
and [`attempt2`](../data/qwen38-q4km-tp2-http-concurrency-20260825-r2-attempt2/).
The fail-closed aggregator produced the
[structured result](../data/2026-08-25-qwen38-q4km-tp2-http-concurrency-r2-result.json),
whose SHA-256 is
`03e91d9fa6a49034e643ca8f4a94b994604c8fe2e04f90848e8a2fb4b9d5cfeb`.
The frozen preregistration remains
[here](2026-08-25-qwen38-q4km-tp2-http-concurrency-r2-preregistration.md).
