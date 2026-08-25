# Qwen3.8 Q4_K_M TP2 output-audited HTTP concurrency R2

Status: **preregistered; not run**.

The non-publishable oracle pilot produced 64 complete cache-zero sequential
responses and a frozen compact oracle digest with SHA-256
`0a9095d3407263150fce9794035c33ed480a0ba04908f793ae6810d4e5567e33`.
Its concurrency rates remain excluded.

R2 requires two new 64-slot TP2 servers. Each independently measures
1/2/4/8/16/32/64 synchronized native HTTP requests with 128 raw output token
IDs per request. Every response must be complete and cache-zero, and no output
may collide with a frozen sequential oracle belonging to a different base
task. Sequential token identity is reported but is not required because batch
shape may change greedy output.

Publication requires both attempts to pass and a relative range of at most
10% at every exact concurrency. The curve uses the two-attempt median; the
pilot is never included. No point may be interpolated or extrapolated.

See the [machine-readable contract](../data/2026-08-25-qwen38-q4km-tp2-http-concurrency-r2-prereg.json).
