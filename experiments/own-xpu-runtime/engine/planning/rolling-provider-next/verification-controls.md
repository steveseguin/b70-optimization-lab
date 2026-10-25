# Future rolling measurement controls

This note proposes a later mode. It does not change the frozen pending-provider
qualification or grant a launch. That gate requires full target restore checks,
full recursive-provider restore checks, and full provider survival comparison
around every target suffix abort. Its diagnostic timings are not throughput.

The next performance mode should have a separate explicit admission flag and
attestation schema. Do not make the pending-proof flag silently mean something
weaker when another verification flag is absent. Preserve the current v4/v5
comparators and receipts as historical qualification evidence.

## Copies and checks that remain

A rolling measurement still uses the same arithmetic and transaction path:

- Validate the complete disjoint target/canonical-provider/private-image census,
  copy-table bounds, immutable row lineage and accepted-seed/final-parent binding.
- Capture every target-owned mutable byte into one of the two checked images;
  restore the oldest rejected suffix exactly once, including host metadata,
  context/bank bindings and shared output bytes. ACCEPT never rewinds execution.
- Advance canonical MTP exactly once for the next verified true pair; capture its
  post-canonical state; run the existing one-step recursive computation; restore
  all canonical device allocations and both pinned buffers from its private
  image. Restore the exact host state and attention extent through the existing
  binding path. Provider private storage remains excluded from target snapshots.
- Retain command/queue/event ordering, completion/error checks, tiny sticky-error
  reads, allocation-identity checks, logical/physical cursor invariants and the
  no-callback borrower checks. Never restore sticky errors, retry failed work or
  run cleanup copies after a partial failure.
- Retain the final-parent lease until the validated op27 reply, because that is
  the first existing wire event proving the read-only peer was captured. Continue
  servicing other owners while stage zero executes provider work. This is host
  orchestration overlap, not simultaneous target/provider compute on stage zero.

These are the checked copy/restore semantics already implemented by
`src/pipeline/ring/checkpoint_ring.hpp`,
`src/pipeline/recursive_provider/draft_runtime_extension.inc`, and
`src/pipeline/recursive_provider/batch.hpp`. A performance switch must not bypass
them or substitute a different arithmetic implementation.

## Diagnostic work that a later mode can omit

The existing `verify=false` restore paths already distinguish restoration from
its expensive proof readbacks. A future explicitly qualified rolling mode can
omit the full target image/allocation readbacks after each abort and the full
canonical provider/private-image readbacks after each recursive restore.
It can also omit `capture_survival`/`verify_survival` around every target abort;
those operations currently read all canonical and private bytes twice and
serialize full host/descriptor identity. These omissions require their own
honest counters: restore counts may be nonzero while full-byte-verification
counts are zero. Never emit `all_aborts_byte_verified: true` or survival-success
records for checks that were disabled. Compact control/ownership checks remain.

Keep independent configuration fields for target full-byte restore verification,
recursive full-byte restore verification, and pending-provider survival
verification. Qualification enables all three. The rolling measurement mode
must record all three explicitly, retain the source/build/profile identity, and
link the corresponding full-verification result. A sampled check, if added
later, must report selected command IDs and actual counts; sampling is not a
full proof and is not proposed for the first rolling gate.

## Qualification and comparison

1. Close the current pending-provider model proof with exact target and all
   canonical draft state. Preserve the two-row and one-row survival receipts.
2. Qualify the asynchronous controller with all three diagnostic controls enabled:
   actual proposals, delayed/reordered replies, accepted-originally-tentative
   seeds, immutable issued recursive guesses, suffix abort, EOS and cap drain.
3. Run the same bounded deterministic request once with the prospective
   measurement controls. Require identical output and final sealed target and
   canonical draft state against the fully checked rolling arm. Verify emitted
   counters distinguish actual copies from disabled readbacks.
4. Only then use a separately qualified persistent-request path for the full
   cold 12-prompt benchmark. Current ring modes refuse RESET; the old wavefront
   persistent wrapper is not an implicit ring capability. Do not replace this
   missing capability with a fresh-server chain.

A final state dump can occur after the timed interval, once all tentative work
and provider leases have drained. Record any diagnostic costs inside the timed
interval. The independent fault observer and per-send admission checks stay
active in every mode.

## Measure before optimizing copy submission

Retained quiescent diagnostics reported head medians of roughly 2.045 ms
canonical provider, 2.007 ms recursive compute, 0.465 ms capture, and 10.051 ms
restore **including full readback verification**. These are not production
restore timings. Do not subtract the last number to manufacture throughput.

Measure checked capture and restore completion time with full readbacks disabled,
plus stage target compute, stage-zero provider occupancy, transferred bytes,
lease wait, rejection waste and committed tokens. The provider currently submits
one checked CopyEngine transfer per device allocation; only after measurement
should a separate patch evaluate the existing SnapshotFlat descriptor approach.
Do not combine that copy optimization with the first rolling correctness gate.

Stage zero performs target and provider work on one ordered device queue. Its
load therefore includes canonical plus recursive work and necessary copies.
The final-record lease and three-global-row/two-pending-row limits can create
bubbles. The common-cohort recursive seed probabilities are useful design priors,
not realized rolling acceptance rates or a speed forecast. Report an observed
matching-workload result before claiming quad acceleration.
