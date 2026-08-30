# Qwen3.8-27B Q4_K_M TP2 queue-settle50 c64 replay: failed

The first fresh-server replay failed the preregistered exact-output gate at **55/64**. The second replay was cancelled by policy, and no WDC candidate ran.

- Frozen c64 oracle: 64 rows, 128 token IDs per row.
- Fresh replay: all 64 requests completed, cached-token counts were zero, and cross-base collision count was zero.
- Exact token-ID identity: 55/64, below the mandatory 64/64 threshold.
- Diagnostic-only aggregate rate: 142.64997566622418 tok/s. It is not publishable.
- Admission trace: four requests launched first; the remaining 60 launched 451 ms later. A 50 ms first-arrival window therefore did not create one c64 cohort.
- Runner defect exposed: the failed exact-output exit occurred before post-run WDC/kernel evidence was written. The raw server log contains no WDC engagement, and cleanup was clean. The runner was fixed so future failures collect all postchecks before returning nonzero and cannot label an unqualified result publishable.

Result SHA-256: `970a41d4f4f31522525c922393aba8acc010b5d321817c1587c95c155e03811b`.

Evidence: `/mnt/fast-ai/bench-results/qwen38-q4km-tp2-queue-settle50-c64-replay-20260830-r1-concurrency-control-attempt1/`
