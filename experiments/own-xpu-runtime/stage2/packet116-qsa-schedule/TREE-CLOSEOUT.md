# Rejected value-tree storage variants

<!-- experiment-closeout -->
Question: can the exact adjacent32 value tree be visited depth first, or stored
as a scalar stack array, to reduce live private leaves while retaining all bytes?
Identity: `iq3-p49-split32-v1`; GNU and Intel CPU builds with no fast math,
contraction or reassociation. These are operator probes, not speed results.

Outcome: closed for this packet. The recursive tree first differs at the
adversarial NaN trial896 under GNU. The fixed stack-array breadth tree passes
GNU but differs at trial896 under Intel. Restoring the original vector helper
passes that tree probe, but the independently scheduled attention body still
changes an Intel NaN output payload (`check1751`, before adding pre-gate checks).
No finite output mismatch was observed before those failures.

Evidence: [recursive source/log](evidence/depth-first-rejected/),
[stack-array source/log and attention failure transcript](evidence/scalar-tree-rejected/).
The third failure’s on-disk log was overwritten before archival; its tool
transcript and reconstructed variant are explicitly labeled, not raw receipts.
Each comparison was raw `memcmp`, not a numerical tolerance. Compiler lowering
can choose different NaN operands despite an identical mathematical tree.

Retained mechanism: eight subgroups score four positions each, versus four
subgroups scoring eight each. The device numerator is restored to production's
vector2 body; first128 threads own it, the other128 help scores. On CPU,
exceptional input uses the unchanged reference body. Finite input keeps the
independent scheduling check and pre-gate FP32 comparison. Device state equality
and the micro kill gate remain mandatory and unmeasured here.

Revisit only with a compiler-level demonstration of unchanged NaN propagation
and raw-byte gates covering both compiler families and actual device state.
