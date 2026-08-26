# Qwen3.8 official FP8 TP2 HTTP concurrency R3

Status: **preregistered; not launched**.

R3 repeats R2 on two new fresh servers. R2 is excluded rather than repaired in
place. The only protocol change is the tested qualifier: pilot mode requires
64 raw token-ID arrays and emits compact digests; publication mode requires the
64 frozen compact SHA-256 rows and validates every new raw response against
them.

Everything else remains fixed: official FP8 weights, TP2, target-only/MTP0,
FP16 KV, four active sequences, one excluded warmup, and exact c1–c64 batches.
Every measured response must contain 128 complete raw token IDs, report zero
cached prompt tokens, and avoid cross-base oracle collisions.

The two new attempts must stay within 10% for aggregate throughput and 15% for
TTFT/end-to-end p50/p95 at every point. c8–c64 include queueing. All published
values are exact-attempt medians; no interpolation or extrapolation is allowed.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-concurrency-r3-prereg.json).
