# D55 preregistration: projection-repair strict replay

Date: 2026-08-31

D54 passed the complete 12-prompt varied suite at a class-balanced median of
24.804756 tok/s, with cached tokens zero, all objective canaries passing, one
output across eight repeated greedy requests, clean shutdown, and no host/GPU
fault. It remains a candidate.

D55 repeats the exact non-instrumented candidate in a new TP1 process and new
cache root. It must independently pass every D54 workload and canary gate. In
addition, all twelve complete token-ID sequences must match D54 by prompt ID;
matching only text previews, hashes, averages, or the first 100 tokens is not
sufficient. Its reported speed remains the median of prompt-class medians.

A pass qualifies deterministic MTP0 correctness for subsequent performance
optimization. It does not authorize claiming the synchronized implementation
as the final fastest lane: the next step is to remove unnecessary barriers,
retest exactness, and then restore TP2/speculative decoding under the same
strict policy.
