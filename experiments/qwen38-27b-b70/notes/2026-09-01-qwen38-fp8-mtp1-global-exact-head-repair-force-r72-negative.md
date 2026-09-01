# Qwen3.8 FP8 TP2 MTP1 R72: divergence is upstream of the target head

R72 forced every target row through the same batch-invariant dot product that
R65 used for the entire vocabulary head. It still reproduced the identical
`cache-c000` c2 token-96 mismatch. The c2 rate fell to 12.758 tok/s, proving
the exact path executed; cached prompt tokens remained zero and the kernel log
had no new GPU/Xe fault.

This closes vocabulary-head repair for the production 64-slot scheduler shape.
The hidden state entering the target head already differs between c1 and c2.
The earlier R65 c2 pass used a two-slot server shape and cannot be generalized
to the production scheduler. The next experiment must trace c1/c2 target model
boundaries and locate the first hidden-state divergence before changing another
kernel.

No R68-R72 value is published or submitted externally. Structured evidence is
in
[`2026-09-01-qwen38-fp8-mtp1-global-exact-head-repair-force-r72-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-global-exact-head-repair-force-r72-result.json).
