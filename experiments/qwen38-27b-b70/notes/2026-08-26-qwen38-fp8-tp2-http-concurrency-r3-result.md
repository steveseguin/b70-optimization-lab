# Qwen3.8 official FP8 TP2 HTTP concurrency R3 result

Status: **qualified for output-audited HTTP aggregate throughput and queued
per-request latency**.

Two new fresh servers independently measured synchronized native HTTP
completion batches at c1/2/4/8/16/32/64. The service admitted at most four
active sequences, so c1-c4 measure active service capacity and c8-c64 include
queueing. Every response returned all 128 raw token IDs, reported zero cached
prompt tokens, and avoided every frozen sequential oracle belonging to a
different base task. Sequential greedy identity varied with batch shape and is
reported, not claimed as invariant.

| concurrent users | attempt 1 aggregate tok/s | attempt 2 aggregate tok/s | published median aggregate tok/s | median per-user tok/s | TTFT p50 / p95 ms | end-to-end p50 / p95 ms | queued |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| 1 | 21.565538 | 21.605051 | 21.585295 | 21.585295 | 89.449 / 89.449 | 5,928.333 / 5,928.333 | no |
| 2 | 41.323878 | 41.370989 | 41.347433 | 20.673717 | 127.086 / 177.017 | 6,145.134 / 6,186.157 | no |
| 4 | 81.109115 | 81.064316 | 81.086716 | 20.271679 | 175.494 / 212.732 | 6,289.904 / 6,313.430 | no |
| 8 | 81.233845 | 81.255815 | 81.244830 | 10.155604 | 3,291.121 / 6,499.807 | 9,430.033 / 12,602.327 | yes |
| 16 | 81.360587 | 81.507721 | 81.434154 | 5.089635 | 9,556.379 / 19,041.603 | 15,698.411 / 25,146.639 | yes |
| 32 | 81.456640 | 81.549443 | 81.503041 | 2.546970 | 22,114.973 / 44,144.486 | 28,259.234 / 50,249.462 | yes |
| 64 | 81.453796 | 81.532484 | 81.493140 | 1.273330 | 47,234.926 / 93,332.472 | 53,384.701 / 99,490.453 | yes |

Aggregate throughput effectively saturates at four active users. Sending 64
requests does **not** raise capacity beyond the c4 result; it raises median TTFT
from `175 ms` to `47.2 s` and p95 TTFT to `93.3 s`. The c64 number is therefore
queue behavior, not evidence of useful 64-way scaling.

The worst aggregate-throughput relative range was `0.1831%`, inside the frozen
10% gate. The worst latency relative range was `1.1354%`, inside the frozen
15% gate. The earlier R2 attempt is excluded because its embedded postprocessor
could not consume the frozen compact oracle; it was not repaired or reused.
The non-publishable oracle pilot is also excluded from every median.

The exact tuple is Qwen/Qwen3.8-27B-FP8 revision
`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, image
`vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`,
vLLM `0.27.2rc1.dev77+gac7509e2b`, two B70s/TP2, FP16 KV,
target-only/MTP0, max model length 4,096, max sequences 4, max batched tokens
256, prefix cache off, and PIECEWISE graph capture size one.

The complete attempts are retained under
[`attempt1`](../data/qwen38-fp8-tp2-http-concurrency-20260826-r3-attempt1/)
and
[`attempt2`](../data/qwen38-fp8-tp2-http-concurrency-20260826-r3-attempt2/).
The fail-closed aggregator produced the
[`structured result`](../data/2026-08-26-qwen38-fp8-tp2-http-concurrency-r3-result.json),
whose SHA-256 is
`20babe2142e3ea215e1b6ae953918c0e8f8c63d662dec563e7c372227b212e51`.
The frozen [preregistration](2026-08-26-qwen38-fp8-tp2-http-concurrency-r3-preregistration.md)
owns the publication boundary. Every published point is the exact median of
the two attempts; no point is interpolated or extrapolated.
