# Qwen3.6 target-Q8/F16 TP1 SYCL-graph exact-depth R3 result

State: **bounded negative at depth 2048; cleanup passed**.

R3 measured depth 0 and depth 2048 before its preregistered graph-evidence
gate stopped the curve. Depth 0 measured 900.310441 prefill tok/s and
19.356325 decode tok/s. Its prefill and decode summaries both replayed every
request with no cache-full events.

Depth 2048 measured 880.776171 prefill tok/s and 19.198522 decode tok/s. The
prefill summary exposed the exact failure: 28 graph shapes were requested with
the frozen cache limit of 8; 8 were recorded and replayed, while 20 hit
`cache_full`. The following decode summary was healthy—641/641 requests
replayed, 639 cache hits and direct replays, and zero cache-full events—so this
is specifically a prefill graph-cache-capacity failure, not a decode failure.

Only depths 0 and 2048 launched. The remaining five contexts must not be
inferred. The R3 run contributes zero cells and carries no curve, publication,
quality, record, submission, or protected-value-replacement authority. All raw
artifact hashes and both exact graph summaries per launched depth are preserved
in the structured result JSON. The immutable output root is
`/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-sycl-graph-exact-depth-20260825-r3`.
