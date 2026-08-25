# Qwen3.8 27B Q4_K_M TP1 HTTP concurrency r3

Status: **passed output isolation; batch-shape-variant**.

R3 preregistered the honest gate after r2 failed strict sequential identity.
It froze r2's cache-zero sequential raw-token oracles by digest, then ran two
new cache-off servers. Both attempts passed: every one of the 254 concurrent
responses contained 128 raw token IDs, every prompt reported zero reuse, and
no generated sequence collided with a frozen oracle from a different base
task. Pointwise relative range was 0.14–2.03%, below the 10% gate.

The published medians are:

| users | aggregate tok/s | per-user tok/s |
| ---: | ---: | ---: |
| 1 | 24.6408 | 24.6408 |
| 2 | 36.5530 | 18.2765 |
| 4 | 49.3161 | 12.3290 |
| 8 | 56.1197 | 7.0150 |
| 16 | 54.9656 | 3.4354 |
| 32 | 65.8029 | 2.0563 |
| 64 | **83.7967** | **1.3093** |

Sequential token identity passed for the one-user point in both attempts.
At every multi-user point, at least one response differed from its sequential
token digest. The output remained complete and task-isolated; therefore this
is a measured capacity curve with a batch-shape warning, not a deterministic
serving claim.

See the [compact result](../data/2026-08-25-qwen38-q4km-tp1-http-concurrency-r3-result.json),
[preregistration](../data/2026-08-25-qwen38-q4km-tp1-http-concurrency-r3-prereg.json),
[frozen oracle digests](../data/2026-08-25-qwen38-q4km-tp1-http-concurrency-oracle-digests.json),
and [runner](../scripts/run-qwen38-q4km-tp1-http-concurrency-r3.sh).
