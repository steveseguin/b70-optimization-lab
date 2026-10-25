# Independent ownership and cancellation review

The reviewed isolated `arbiter.py` and `coordinator.py` have no identified
ownership/drain blocker. This conclusion applies to the source hashes in
`engine-audit-review.json`, not to future socket integration or GPU arithmetic.
No frozen native/controller files were edited and no GPU operations were run.

The existing eleven tests passed. An additional deterministic 1,000-schedule
check passed with prompt lengths 1/2/3/4/8/31/32/33/64, stage counts 2/3/4/6,
short output caps, random EOS tokens, first/second-depth misses, fresh-canonical
proposal disagreement, and explicit cancellation. Noncancelled runs match
reference target histories and outputs and execute exactly one provider step
per consumed true pair. Cancelled runs emit no additional output and drain all
pending target work. `review_schedules.py` reproduces this additional check.

The final-parent lease prevents a new final ROW until op27 completion. It does
not manufacture an in-flight command, so rejection drain remains possible.
Stage-zero ACCEPT cannot overtake the next canonical seed. Auxiliary command27
uses the core's one wire-sequence allocator and actual busy slot; its reply must
match the unchanged borrowed target cursor and suffix IDs before release.
Already-issued recursive tokens remain immutable if a fresh d1 differs; only a
final target ACCEPT changes token truth. A wrong parent invalidates its suffix.

Cancellation preserves locally committed and in-flight ACCEPT prefixes, waits
for an already-reserved provider operation, and releases an unused parent lease
only for explicit cancel/reset intent. Ordinary misses retain the lease until
the corrected seed can advance the provider. EOS/cap do not compute a provider
step for an unused output token. The model refuses native RESET rather than
claiming that the older persistent wrapper applies to this ring protocol.

The socket integration must keep every reserved command owned through a stop
arriving before send; a reservation cannot simply be removed from the returned
batch. The bridge author confirmed its event loop will check stop between
iterations and finish sending/draining commands already reserved. The typed
Parent/result inputs also remain a codec boundary: exact peer, raw-hidden,
request/epoch/seed/final-commit/provider-serial validation must precede completion.

`cancelled_provider_incomplete` is a conservative qualification exclusion.
Abandoning a parent-only lease may set it even when the already-consumed provider
prefix happens to match the final target prefix. It must not be reported as a
measured numerical mismatch. Such cancelled requests should not enter normal
completed-request correctness or speed statistics.

When promoting this prototype, replace its two copied reservation loops with
reviewed generic admission hooks to avoid divergence from the core scheduler.
Real fragmented socket tests, native overlap qualification, final-state parity,
persistent request semantics and actual throughput remain separate gates.
