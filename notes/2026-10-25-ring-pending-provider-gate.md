# Next gate: canonical draft advancement with pending target snapshots

Design only. The native/core source at `62b4c1143` is frozen for the current
quiescent ring-live build and model replay. This note changes no code, launch,
service, device state, or approval boundary. The gate below is contingent on that
replay passing full target/draft state and actual d1/d2 checks.

## What this gate must establish

A target suffix may have been checkpointed before the canonical provider advances.
Rejecting that suffix must restore only target-owned state. It must leave the
newer canonical provider, its private recursive image, and its host/proposal
identity unchanged. Existing scripted ring correctness and quiescent recursive
restoration prove the two components separately; they do not prove this combined
ownership boundary.

Use one continuously loaded, bounded qualification run. Scripted tentative target
inputs are allowed solely to force the required rejection geometry. Actual MTP
d1/d2 still come from the existing provider and are recorded, but need not drive
those test rows. No speed claim follows from this gate.

## Minimum two-slot sequence

Let S be the verified input at absolute position q. Its independently committed
final parent is at q−1. Target positions count processed inputs; provider position
uses the existing true-pair convention.

| Boundary | Stage-0 logical position | Stage-0 physical position | Canonical provider position | Pending target rows |
|---|---:|---:|---:|---|
| S executed and ACCEPTed | q+1 | q+1 | q−1 | none |
| Tentative T at q+1 completed | q+1 | q+2 | q−1 | T |
| Tentative U at q+2 completed | q+1 | q+3 | q−1 | T, U |
| op27(S) completed and recursive branch restored | q+1 | q+3 | q | T, U |
| One ABORT_SUFFIX(T) acknowledged | q+1 | q+1 | q | none |

1. Retain the independently final-owned COMMIT record for q−1. Execute and ACCEPT
   S on stage 0, saving its complete output bytes before any newer ROW can
   overwrite the shared output slot. S is the local last-accepted seed throughout
   this borrow.
2. Execute T and U only on stage 0 initially. Both are tentative, completed and
   unresolved, with exact immutable parent/prefix identities and distinct ROW
   tickets. Choose T deliberately wrong for the qualification; U is its child.
   Their snapshots are taken while provider position is still q−1. Keep S, T, U
   within the existing three-global-row bound. No tentative final-stage input is
   allowed.
3. Admit op27(S) under an additional explicit pending-provider gate. Only stage 0
   submits during this command. It performs the canonical true-pair step q and
   the existing one-pass recursive proposal, then restores its own hypothetical
   branch. Its reply must report canonical position q and the next provider
   serial while target physical/logical positions remain q+3/q+1.
4. Hold the next final ROW until op27 replies. The current protocol has no early
   peer-capture acknowledgment: only the full reply proves the independent final
   record and raw hidden were captured and the provider transaction completed.
   The final record's marker is invalidated by the next final ROW, so releasing it
   earlier would create a provenance race. A future early acknowledgment is a
   separate protocol change.
5. Forward the retained output of S through the remaining stages as verified
   work. The final output for S supplies actual truth for T's input. Check the
   deliberate miss against that output; the reference token list is not a
   substitute for target verification. T/U need not be forwarded in this minimal
   ownership gate.
6. Freeze descendant admission. With all issued work drained, send exactly one
   ABORT_SUFFIX for T. Require its ACK to name both original global IDs T and U,
   report physical=committed=q+1, pending=0, and the requested full target restore
   check. Do not restore once per child, repeat a provider step, or replay target
   work to manufacture matching state.
7. After the complete abort ACK, use fresh global IDs to replay the corrected
   target suffix. Keep provider serial q unchanged until the next genuine
   canonical true pair is due. Continue to the same fixed output cap as the
   accepted quiescent reference and compare every target and canonical draft
   buffer and meaningful host field.

The provider's new private image contains the post-canonical q snapshot. It must
remain byte-identical across step 6 even though neither target checkpoint contains
it. A check only after a subsequent op27 would miss a rollback bug that the later
provider run overwrote.

## Exact evidence at the ownership boundary

The current DUMP correctly refuses pending target rows. Do not weaken DUMP to
capture an ambiguous speculative state. Instead, add a qualification-only native
survival check around the existing target abort:

- Before abort, with no provider transaction, callback or queued borrower, capture
  every declared canonical provider device allocation, both pinned allocations,
  and the separately declared private image into bounded host-owned comparison
  storage. Use the actual validated inventory and byte extents, not a hardcoded
  allocation count or name-prefix exclusion. The current model has 71 device and
  two pinned canonical allocations; that count remains evidence, not an API.
- Capture the full provider host snapshot used by the recursive implementation:
  position/extent, owned reverse bytes, pending/queued/publication metadata and
  inactive callback/event ownership. Include provider serial, accepted seed and
  prefix, last successful proposal metadata, private snapshot status and the
  provider capture/restore/verification counters. The sealed draft JSON alone is
  insufficient because it does not serialize every owned host byte/reference.
- Perform the existing one-shot target suffix restore, without submitting any
  provider computation between captures. Compare the provider bytes and owned
  host/identity fields exactly afterward. Record the compared inventory hash,
  byte totals, provider position/serial, seed, rejected IDs, and before/after
  evidence hashes in a bounded abort-survival receipt. Zero counters or an
  unchanged allocation census alone do not prove preservation.
- Preserve target restore-byte verification, canonical bank mapping and target
  metadata checks. Shared profiling/submission counters naturally accumulate
  diagnostic work; do not mistake them for provider-owned canonical model state
  or roll them backward.

No new device allocation may occur after the target ring census freezes. The
survival comparison storage is host-owned and qualification-only; it is not part
of target snapshots or canonical draft serialization. A mismatch or sticky error
must halt the gate without another request, automatic repair or restart.

## Boundaries worth covering in the same small run

For the existing 87-token prompt and 32-output fixture, seed q=95 places tentative
target input 96 across an attention extent boundary. Seed q=96 places the
provider's recursive call across its own extent boundary before restoration.
Compute these choices from the actual extent geometry when generalizing the
fixture; do not encode those positions as engine constants.

The minimum gate above proves a two-row discarded suffix. Before admitting both
pending depths generally, also exercise one pending row after an older ACCEPT:
issue a correct T and wrong U, borrow for S while both are pending, obtain actual
truth for T, then ACCEPT T without rewinding physical target position. Its new
canonical provider step may run while only U remains pending. Reject U once and
require that still-newer provider state/private image to survive. This can share
the same loaded owners and bounded request; it does not need a server chain.

The physical snapshot manager and scripted ring already support these states.
The new work is admission and evidence, not another target executor or a change
to reductions, quantization, target arithmetic or model training.

## Narrow implementation surface after the current gate

- In [dispatcher.hpp](../experiments/own-xpu-runtime/engine/src/pipeline/ring/dispatcher.hpp),
  preserve today's quiescent ring-live mode. A separate flag can allow op27 only
  with completed tentative pending records under the validated independent
  partition. Replace the empty-boundary requirement with explicit drained-owner,
  pending-inventory, logical-seed and physical-cursor checks; do not simply delete
  `ring.boundary()`/`checkpoints.boundary()`.
- [StageRing::draft](../experiments/own-xpu-runtime/engine/src/pipeline/ring/stage_ring.hpp)
  already requires independent partitioning and tentative pending records and
  checks that physical position does not change. Add the needed observable pending
  identities/counts rather than borrowing or mutating its private queue externally.
- The [checkpoint manager](../experiments/own-xpu-runtime/engine/src/pipeline/ring/checkpoint_ring.hpp)
  must continue excluding canonical provider, pinned provider and explicit private
  image IDs. Its complete target census remains immutable. Do not add provider
  bytes to canonical target checkpoints to simplify rollback.
- Reuse [native provider admission](../experiments/own-xpu-runtime/engine/src/pipeline/recursive_provider/admission.hpp)
  and the [readonly final peer](../experiments/own-xpu-runtime/engine/src/pipeline/recursive_provider/peer.hpp).
  The seed still comes from the locally ACCEPTed row, the parent from the final
  owner, and the relayed header/payload must match both independent records.
- Add the bounded abort-survival verifier beside the provider ownership code. A
  first CPU fixture should take two target snapshots, advance the actual provider
  snapshot helper, restore the older target image once, and compare all newer
  provider/private bytes and metadata. Include missing/overlapping private IDs,
  pending callbacks before drain, one-slot-after-ACCEPT and extent transitions.
- Add a distinct state-set mode/version for pending-provider qualification.
  Preserve v4's `quiescent-target` and zero-tentative requirements. Record actual
  provider borrows at pending depths 1 and 2, survival checks, full target suffix
  receipts and the independently bound canonical draft/private inventory. Do not
  relabel current v4 evidence or infer the number of borrows from configuration.

Only after this gate should the asynchronous coordinator consume actual d1/d2
for rolling target work. Preserve issued recursive lineage when a fresh canonical
guess differs; invalidate every descendant of an actually wrong parent. Keep the
existing maximum of three global positions and final-stage verification rule.

## Copy-cost follow-up is separate

The current provider deliberately uses one checked CopyEngine copy per canonical
device allocation per capture/restore. Its trace records `canonical_ms`,
`capture_ms`, `recursive_ms` and `restore_ms`, plus snapshot bytes and verification
status. First inspect those measurements from identical true-pair/head/context
cohorts. Report head-off and context-censored batches separately; do not treat
byte-verification readbacks as production restore cost or reuse discarded-probe
acceptance rates as a rolling throughput prediction.

If copying is material, a later opt-in change can precompile checked descriptors
into a flattened copy operation, reusing the target checkpoint mechanism. Its
private image and descriptor tables must all be allocated and explicitly
classified before the census freezes. Preserve the current copy path and its
measured recipe, then repeat exact provider/target survival checks before timing
an identical request. A faster snapshot is useful only if the complete rolling
schedule improves; this note predicts no speedup.

## Actual four-card result

The bounded run passed with native binary
`8e03d3cd67fc99c7db4408cb9c2e6abb158806f142df16292ece37083e706231`.
All 32 output IDs, 2,065 target buffers and 73 canonical draft allocations match
accepted replay. All 117 true pairs and 32 recursive predictions match the
retained reference. Both target suffix restores were byte-verified.

The first abort retained canonical provider position 95 after discarding two
rows whose snapshots were taken at provider position 94. The second retained
position 97 after discarding one row captured at provider position 95; the
older tentative row had been accepted without rewinding the remaining suffix.
Provider attention extents were 96 and 128 respectively. Complete canonical,
pinned and private bytes plus host/Sequence/exposed prepared bindings survived.

All four workers exited zero. Across 75 passive samples, the 14 known fault
signatures stayed unchanged; minimum available host memory was 72,047,874,048
bytes. No host settings changed. Actual recursive proposals were still discarded;
scripted target inputs forced these rejection cases. This is a correctness
qualification, not rolling inference or a speed result.

The [independent v5 proof](../experiments/own-xpu-runtime/research/continuation-2026-10-25/ring-pending-provider-proof/RESULT.md)
retains full command lineage and native survival records. Actual overlapping
proposal consumption is the next gate, using existing draft weights only.
