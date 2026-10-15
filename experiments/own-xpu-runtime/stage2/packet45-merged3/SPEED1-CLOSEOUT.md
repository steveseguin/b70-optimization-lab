# Packet 45 SPEED1 — closeout

<!-- campaign-closeout -->

## Question and identity

On 2026-10-15, repair the two leading costs identified in the accepted
[regression analysis](REGRESSION-ANALYSIS.md), starting from `e55ffc96e` and the
qualifying `f912fdaf6` artifacts. Same Unsloth UD-IQ3_XXS weights, full BF16 cache,
`iq3-p17-detmath-v2`, controller, placement and oracle. CPU-only work; coordinator
owns every device launch. `build/results-f912fdaf6/` and `build/incident-*` were
read only.

## Outcome

**Batching and the small-FFN repair are ready for device qualification. Requested
whole-buffer writer exclusions were rejected, not implemented.** Write-before-read
is insufficient for the unchanged full-state contract: the original bytes must
also survive a terminal discard or cancellation. No state hash or exactness check
was weakened, and no byte-reduction claim is made.

At context 4096, position 100, each capture and each restore now submits:

| Draft placement | Bytes (MiB) before → after | Submissions before → after | Required component extent checks |
|---|---:|---:|---:|
| Rank 0 | 343.850 → 343.850 | 936 → 32 | 936 |
| Rank 1 | 354.970 → 354.970 | 1,022 → 34 | 1,022 |

These are source/metadata counts, not measured device timings. Positions 128 and
214 have the same submission counts and the original position-dependent byte
extents. Hit acceptance performs no restore. A miss/cancel performs both legs.
The shared 65,536-byte host slot remains separately preserved.

The production plan now ignores only the P39 `shared-up-act-q6/q8` rewrite.
The selected `p30.small.rows4` tuple forms on all 48 target layers: two commands
per tuple including its activation, instead of six. **192 extra target commands
are removed.** K2 measurement/selection rules and all other P39 branches remain
unchanged; the isolated shared-up fixtures remain available. This is a schedule
count, not a measured speedup.

## What worked

[Snapshot transport](strict_snapshot.hpp) first prepares every original bounded
copy through the unchanged `CopyEngine::copy` guard in `owner.cpp`. It batches
independent validated descriptors into at most 32 extents and 128 MiB per
submission. Multi-extent batches use a byte-copy kernel; singleton batches retain
the prepared copy. The kernel capture is checked by the existing 1024-byte build
limit. Device owner bindings, dependencies, liveness and drain paths remain in
force. Source allocation IDs are distinct and backup ranges do not overlap.
The two full 128 MiB scratch chunks still use singleton copies. Under the inline
32-descriptor bound, the schedules attain the minimum 32/34 submissions.

Owner/device allocation sizes, backup capacity, source extents, bank/QSA rules, shared slot,
launch metadata and sticky-error behavior are unchanged. Consequently the
retained production allocation/storage census remains applicable. The audit
rebind explicitly checks the new bounded copy-site inventory; it does not label
historical execution as a new run.

[Mini gate](speed1-snapshot-gates.json): 42 executions, 36 checks: hits, misses,
normal/wrong MTP, terminal cancellation at start/middle/end/full completion,
request-boundary retirement, both controllers and both draft placements. The
32-token terminal prompt crosses the prepared launch extent from 32 to 64.
All target allocations, inactive banks, invalid cache tails, standalone scratch,
bank/launch/lookup metadata and the shared slot compare with the never-speculated
reference. Raw event telemetry remains recorded separately. Confirmed draft
state agrees for normal versus wrong MTP. Four deliberate omissions of the
required `streams` extent are rejected by that same full-state comparator.

[Plan sweep](speed1-plan-gates.json): 48 metadata-only rows for both device-measured
dispatches and forced all-fusions, target rank 0/rank 1, KD/draft owner, contexts
4096/32768 and draft placements 0/1. No model payload or arithmetic was read/run.
Every target row restores the expected 22/26 or 24/24 small-FFN groups; shared-up
activation tags are zero and other P39 tags remain recorded.

GNU, device and ASAN incremental builds all pass. GNU took 33.5 s, device 40.9 s,
ASAN 104.6 s; at most two compile jobs. ASAN is required by
`seal_context.py:83`. No real-model CPU suite or compiler matrix ran.

## What failed or remains uncertain

The requested blanket exclusions do not pass their proof obligation.
`main.cpp:853` explicitly notes unused scratch tails; plan input/output labels
are not complete byte-store footprints for the standalone workspaces.
Furthermore, `streams` has a first-writer before its first reader, yet deliberately
omitting its restoration changes terminal full-state bytes on every tested
placement/controller. A write-before-read proof would support execution from
private speculative storage, but cannot recover overwritten original storage.
Cancellation permits prefixes that stop before later writers.

The checked [writer audit](speed1-snapshot-inventory.json) records every source
extent, first writer/reader where metadata supplies one, allocation size and
unknown coverage. It admits an empty exclusion set and preserves every byte.
The compressed [per-extent artifact](evidence/speed1/writer-proof.json.gz) is
hash-bound. Partial/unknown coverage is rejected. Safe byte reduction needs
private speculative storage or a separately proved modified-range backup;
that broader implementation remains pending the owner's requested clarification.

The new copy kernel and repaired composition still need coordinator device
exactness and timing. No savings in milliseconds are claimed. In particular,
32/34 submissions are not 32/34 contiguous allocations; they carry the same
936/1,022 checked source pieces. Snapshot byte traffic is unchanged.

## Evidence and patches

- [SPEED1 plan gate](speed1_plan_gate.py), [mini gate](speed1_snapshot_gate.py),
  [production inventory](speed1_snapshot_inventory.py), and
  [strict evidence rebind](speed1_qualification.py).
- [Named seal-6 amendment](seal6-amendment.json): SPEED1 extension pins exactly
  `p39_plan.hpp` and `strict_snapshot.hpp`; the prior fix-6 `main.cpp` pin remains.
  All other compiled-source changes are refused. Historical real-model and
  compiler evidence keeps its original artifact identity. Passing W2m, WS, WSs
  and WS128x windows against the immutable oracle remain mandatory speed
  publication evidence for the new identity.
- [Build/gate logs and retention instructions](evidence/speed1/RETENTION.md).
  The preliminary mini screen is preserved separately; the final gate crosses
  the actual 32→64 admission boundary. No failed evidence was discarded.
- [Binary identities](BINARY-HASHES.md), [CPU seal](cpu-tests.json),
  [build seal](build-receipt.json), and [detached admission binding](window-seal-binding.json).

## When to revisit

The coordinator runs the unchanged qualifying chain and oracle checks on the
new artifacts, then compares snapshot command envelopes and natural hit/miss
cycles with `f912fdaf6`. The expected benefit is fewer submissions and the
removed FFN commands; only that A/B can establish the speed gain. Do not apply
whole-buffer exclusions until byte preservation on terminal rollback is proved.

Final seal identities (SHA256):

| Receipt | SHA256 |
|---|---|
| build-receipt.json | `a199dffa53d9f31e30c1b805ffa251694829bc0beb57d7f7322dc998eccc8c28` |
| cpu-tests.json | `1389d2ad7537f67832ef0c1d722b97281040c80a3f2e9fc43c3052cf73d04ee1` |
| seal6-amendment.json | `ea0c4856446484ae23b3a217bbef76f646b8468b230ca26338bc14dda8765e3e` |
| window-seal-admission-gates.json | `3375baf7f466f176c6699fe8c4f81235bc00e5729ab8352df1dab6c61ea2c1a6` |
| window-seal-binding.json | `2208f25bf12cee99584dbc105f815f3a9d3d962e21f72e232373d6bad0cc8bc9` |

All five device binaries changed, along with five GNU and five ASAN targets.
Every changed artifact linked after the final compiled-source edit. Protocol/ABI
files are unchanged. The seal binds 36 gate receipts; fresh tests include 9 reuse,
11 amendment, 8 audit-mutation, 45 seal-binding and 88 blocked-launch admission checks.
