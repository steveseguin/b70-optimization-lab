# Qwen3.8 FP8 TP2 MTP1 R71: selective exact repair still misses c2

R71 replaced ordinary M1 replay with the proven batch-invariant dot product
for globally ambiguous target rows. It clearly executed—the c1/c2 rates fell
to roughly 37 and 48–59 tok/s—but both c2 repeats still diverged at the same
`cache-c000` token 96. The strict harness failed closed, cache use was zero,
and no GPU/Xe fault occurred.

The remaining bounded control is to force every target row through the exact
repair. That reproduces R65's mathematical scope while retaining R71's actual
greedy-path integration. A passing forced control would prove the selector is
incomplete; a failure would move the cause before the target head.

Structured evidence is in
[`2026-09-01-qwen38-fp8-mtp1-global-exact-head-repair-r71-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-global-exact-head-repair-r71-result.json).
