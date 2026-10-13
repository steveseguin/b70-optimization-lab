# Draft placement and rollback

Only rank1 target head/argmax can publish a token. There is at most one outstanding
guess. Rank1 copies its final layer streams for position p-1 to a dedicated shared
slot and release-publishes the position before enqueueing final normalization,
head and argmax. Rank0 acquires that position and uploads the stream into the
draft's private merge.hidden buffer once x_p is confirmed. The upload completes
before the source slot can be reused by rank1. The forward slots are separate.

Draft rank0 has its own output-head copy and official draft layer weights/cache.
SpeculativeImage is constructed before the provider, so its rollback never rewinds
the confirmed draft prefix. All draft allocations remain in request reset and
final inventories. Both target recurrent-bank launch extents follow their banks.

A target half checks cancellation before every compute launch. A mismatch drains
all submitted work, restores its exact snapshot (including invalid cache tails),
restores history and bank selection, and repeats using the target token. The
snapshot precedes context admission. Rollback restores both launch extents and
rebuilds both banks' QSA command bindings through that same admission path.
Restoring only the cache bytes would leave a terminal bucket crossing observable. Sticky
owner/device errors are fatal; only a draft-provider failure means no guess.
Terminal EOS discards any unneeded half without changing the emitted stream.

On a hit, target acceptance happens before rank0 draft submission, avoiding an
accept-time drain that would serialize draft and rank1's next half. Native draft
read-back uses its own pinned result and completion sequence. Rank1 placement
retains packet40's async draft-before-half path. Python is the synchronous
reference controller. Transfer, cancellation, rollback and misses belong in time.

Balance uses measured aggregate half times 16.6/17.1 ms and draft2.85 ms. Moving
two layers, estimated at16.6/24 ms each, yields18.0667/18.4833 ms. These estimates
omit transfers, host costs and misses; per-layer profiling and actual end-to-end
measurements remain coordinator gates, not CPU speed claims.
