# Qwen3.8 official FP8 TP2 p64 HTTP confirmation R5

Status: **preregistered; not launched**.

R5 tests the promising R4 p64 diagnostic on two wholly new fresh servers. The
R4 rate does not enter the R5 aggregate.

The exact service remains official FP8, the digest-pinned vLLM XPU image, TP2,
FP16 KV, target-only/MTP0, 4,096-token capacity, 64 active sequences, 256
batched tokens, prefix cache off, and size-one graph capture. The frozen
c1/2/4/8/16/32/64 ladder uses unique short prompts and 128 outputs; every point
is within the configured active-slot limit.

Both attempts must pass complete-output, cache-zero, compact-oracle isolation,
and clean teardown gates. Aggregate relative range must be at most 10% at every
point. TTFT and end-to-end p50/p95 relative ranges must each be at most 15%.

If every gate passes, publication uses exact two-attempt medians. Nothing is
interpolated or extrapolated.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-p64-confirmation-r5-prereg.json).
