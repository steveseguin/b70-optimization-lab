# Qwen3.8 Flash-Next HC-up grouped S3g result

Date: 2026-08-31

Status: all-97 M64 exact component pass; source-dispatch design authorized

S3g completed all 194 isolated arms. Grouped E=1 matched the contiguous BF16
authority byte-for-byte for all 97 real target HC-up weights at M64. Every arm
was finite and internally repeatable; all 194 receipts returned zero and bound
one driver PID/nonce, the frozen model and weight manifest, the staged runtime,
and identical before/after loader closure. Independent evidence review found
no blocker.

The fixed-order descriptive timing was uniformly favorable at this production
chunk size:

- authority cross-weight median: `37.978688 us`;
- grouped cross-weight median: `21.588938 us`;
- median per-weight reduction: `42.822%`;
- per-weight reduction range: `8.807--55.103%`;
- grouped faster weights: `97/97`;
- sum of the 97 per-weight median savings: `1363.429844 us`.

Those numbers are component timings, not an endpoint projection or throughput
claim. Provider order was fixed, and this run does not prove how many M64
invocations occur in a complete request.

Raw summary SHA-256:
`2d85c185d6cf4b9e431da55b602bfb54b7fa26b67c0fe5eff963716107502c0a`.
The structured result is
`data/20260831-hc-up-mgt1-grouped-s3g-result.json`.

Under the frozen interpretation, this pass authorizes only the design and
focused testing of a default-off M>1 grouped dispatch over the existing
single-storage integration. It does not authorize a runtime rebuild, full
model load, endpoint launch, speed claim, or change to protected results.
