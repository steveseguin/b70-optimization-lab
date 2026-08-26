# Qwen3.8 official FP8 TP2 HTTP concurrency R2

Status: **preregistered; not launched**.

The oracle pilot passed its 64/64 sequential completeness and cache-zero gate.
Its compact token-ID digests are frozen by SHA-256; all pilot performance and
latency values remain excluded.

R2 uses two new fresh servers, one excluded warmup per server, then exact c1,
c2, c4, c8, c16, c32, and c64 batches. Every response must contain 128 raw
token IDs, report zero cached prompt tokens, and avoid matching the sequential
oracle of another base task. Batch-shape changes from the matching sequential
answer are allowed and reported because TP2 greedy output is known to be
batch-shape-dependent.

Throughput must remain within 10% between attempts at every point. TTFT p50,
TTFT p95, end-to-end p50, and end-to-end p95 must each remain within 15%.
c1-c4 fit the four active service slots. c8-c64 include queueing and must be
labeled that way anywhere they appear.

All published values are medians of the two exact attempts. No interpolation
or extrapolation is allowed.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-concurrency-r2-prereg.json).
