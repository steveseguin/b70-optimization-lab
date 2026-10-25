# Next wavefront depth: two speculative rows, then continuous drafting

Design and CPU protocol model only, 2026-10-25. The active native/controller
files remain unchanged. Preserve the proven single-pending-row path as the
runtime default. The model in [wavefront_ring.py](wavefront_ring.py) is not a
native implementation, a complete distributed scheduler, or a speed result.

## Recommended order

Use depth two (one verified input plus two guessed successors, three global rows)
for the next bounded correctness proof. An early stage needs two unresolved
speculative checkpoints; depth three/four global rows needs three. Three rows
cannot occupy all four stages simultaneously, but a fourth row can cost more
additional draft work than the occupancy it gains. Measure before increasing it.

A burst implementation that freezes canonical draft state until the entire ring
empties is a useful rollback proof. It is unlikely to be the desired final speed
path: every burst drains and then refills the pipeline. Prefer proving an explicit
target/draft state partition before investing in burst throughput tuning. That
partition permits canonical draft steps between target commands while earlier
speculative target checkpoints remain live.

## Physical completion is not logical acceptance

The existing [HALF implementation](../src/gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp)
already increments device position in the executed plan and swaps stage-zero
state banks before its ROW reply. COMMIT publishes retained evidence and releases
ownership; it does not execute the model's position increment.

The ring therefore has two cursors:

- `physical_position`: next row the device can execute after its completed work;
- `committed_position`: oldest input not yet accepted by the verified target.

After rows n+1 and n+2 finish, accepting n+1 only frees its oldest checkpoint and
advances the logical cursor. It must not restore n+1's checkpoint, undo its bank
swap, or move the physical position backward from n+3. On rejection of n+2,
restore the checkpoint captured immediately before n+2. It already includes the
physical effects of accepted n+1. If n+1 is rejected, restore its checkpoint once
and invalidate n+1 and n+2 together, even if n+2's token happens to match later.

Keep one actual command executing per device owner. Allow up to two completed,
unresolved tentative row records; each owns its original Candidate, stream bytes,
checkpoint slot, absolute position, token, fixture, ROW ticket, parent lineage,
and branch generation. Resolve only the oldest row. Final-stage inputs remain
verified-only and its outputs become visible only after its COMMIT reply.

## Snapshot ring mechanics

Do not instantiate two current [StageCheckpoint](../src/pipeline/checkpoint.hpp)
objects. Each constructor freezes `e.allocations.size()` after allocating its
backup/tables; constructing another invalidates the first inventory and may
cause private snapshot storage to be snapshotted recursively.

Use one manager with one validated model-state layout and all ring storage
allocated before the census freezes. It owns two backup regions and checked copy
tables, separate per-slot host metadata/bank maps/output bytes, a free-slot list
and an ordered pending-ticket list. Register private ring allocation IDs explicitly
and exclude that exact inventory from model-state capture. Keep aggregate memory
admission, per-allocation extents and both copy directions checked. Report capacity,
used slots, ticket identities and total bytes; do not infer fit from packed weights.

ACCEPT frees only the oldest slot after exact identity/verified-token matching.
ABORT_SUFFIX first drains the owner's outstanding command, refuses sticky errors,
restores the oldest rejected checkpoint and invalidates all dependent slots and
stream publications. Other stages may have completed different amounts of the
same suffix: restore the matching oldest executed rejected row at each affected
stage, and invalidate unexecuted descendants without inventing a checkpoint.
Admission of corrected work resumes only after every affected stage acknowledges
suffix retirement. No late ROW reply or reused output slot can revive old lineage.

A new opt-in protocol version should carry a shared immutable row identity and
parent identity in bounded metadata, while retaining stage/final/socket sequence
checks. Current native request tickets are local socket sequences, which differ
across stages once draft commands consume stage-zero sequences. Do not silently
use those as cross-stage lineage. Pin a branch generation for late-publication
rejection; preserve generation monotonicity when a corrected token reuses a position.

DUMP/FINISH/EOS require all suffixes drained, zero live slots, equal physical and
logical cursors and matching bank/extent metadata. Existing v1 attestations must
not claim this stronger protocol without an explicit schema/version extension.

## Canonical draft and recursive proposal branch

Reuse [DraftRuntime::compute and the qualified recursive backup/restore](../src/gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/mtp.hpp).
A committed true pair (raw final-layer hidden p, verified token p+1) advances the
canonical draft and yields d1 at p+2. A recursive pass using d1 and hypothetical
draft hidden yields d2 at p+3. Restore the complete recursive branch to the
canonical post-true-pair state before allowing the next true pair. Even an all-hit
proposal chain does not turn its hypothetical hidden states into canonical ones.

Each proposal batch needs its verified seed position/prefix identity, exact
preceding proposal tokens, depth, slot generation and restoration completion.
A d2 token cannot be used after its d1 parent missed. Rejoin retained depth-probe
traces on a common eligible cohort for cost modeling; the published d1/d2/d3
prefix denominators differ because response endings are censored. See
[wavefront-next.md](wavefront-next.md) for the exact counts and limitations.

In the simplest proof, capture all target+draft state as today, freeze canonical
draft while any target slot survives, and queue owned true-pair handoffs until
the ring empties. Recursive backup/restore must complete before opening a target
slot. This establishes correctness but explicitly includes burst refill bubbles.

## Concrete target/draft ownership partition for rolling operation

The source audit found the current MTP arithmetic already owns its caches,
mutable tensors, `scratch`, `control`, `score`, `probability`, `head_workspace`
and `head_fp32`. Its `prepared`, `issue_sites`, `context_extent`, `position`,
publication event/flags, queued probe fields and owned reverse-hidden bytes are
private to DraftRuntime. Constructor checks already reject aliasing with target
plan buffers and target weight IDs. Strengthen this to the complete target write
inventory, including buffers outside the plan map.

Expose a typed provider inventory with distinct mutable device IDs, pinned IDs,
immutable borrowed IDs, and recursion-private storage IDs. Validate live allocation
identity, owner, extent, category, disjointness and complete membership against
the arena. Never infer exclusion from a label prefix. Pinned publication and
half-staging require explicit IDs because **Engine::allocations contains only
device allocations**; the rejected v1 live integration and its exact retained
sources document this previous mistake.

A target-only ring then snapshots all target persistent/scratch bytes and target
metadata, excluding that exact provider-owned set. A draft branch snapshot covers
all draft mutable bytes and draft metadata; neither snapshot restores the other
operator's state. Shared immutable weights/rope may be borrowed by both.

| Shared field/resource | Current use and required separation |
|---|---|
| `e.fp32_sources`, `e.fp32_extents`, `e.fp32_inputs` | Target conversion cache. Current mtp.hpp does not read/write these: draft conversion uses private `head_fp32` and `head_workspace`, and calls its direct kernels instead of Engine's target matrix path. Keep target bytes and metadata together in target restore; assert no provider access when adding variants. |
| Target history, lookup IDs, selected experts, loaded layers, active/spare banks, both target attention extents | Target-owned and restored by target ring. Draft reads a bounded embedding row directly through immutable model weights; it does not call target `prepare_token`. |
| Draft position, draft attention extent and private prepared commands | Draft-owned; advance on true pairs or restore only a recursive draft branch. Target abort must leave the newest canonical values untouched. |
| `tail`, `tail_card`, `card_tails`, `pending`, device event retirement | Shared submission owner. Interleave only at drained command boundaries, including when target *snapshots* remain live. No simultaneous target/draft submission or callback; never restore stale events. |
| `current_cls`, `draft_timing`, `preparing_commands`, `fresh_arguments` | Shared transient execution/attribution context. Use an explicit scoped borrower, assert idle entry/exit, restore prior class, and never leave capture mode active. Draft extent changes rebuild only its private commands. |
| `progress_pending`, callback, publication event | Current live path is synchronous and these must be clear at interleave boundaries. Async drafting is a separate ownership change, not required for rolling target checkpoints. |
| Engine pinned upload/readback slab | Shared transport scratch, fully consumed before drained return and overwritten before reuse; not recurrent operator state. Prove no event/reference survives a borrower switch. |
| `poisoned`, target/draft error state, cancellation | Sticky. Any failure halts admission; no checkpoint or recursive restore clears it. |
| Timing totals, event IDs, submission counts, file traces | Monotonic evidence, never rolled back as model state. Separate per-operator accounting so extra work remains measurable. |

A small reusable `OperatorStateInventory` plus scoped submission ownership is a
better first extraction than separate full Engine instances. It preserves the
current checked kernels, immutable weight store and device lifetime owner while
making model/quant/operator-specific state explicit.

Required partition proof: capture target before an intentionally wrong row;
execute it; advance canonical draft using a newer genuine final-stage true pair;
abort target; verify target matches its earlier snapshot **and** all newer draft
bytes/metadata still match a separate sequential true-pair reference. Repeat
across the 31/32/33 attention extent boundary and both bank parities. Add the
inverse recursive-draft restore test while target state remains ahead. Full-byte
verification belongs in qualification, not headline throughput measurements.

## Cost bounds, not speed predictions

Use separate measured components. The current working estimates supplied for
planning are target stages about 8–10 ms each, a draft pass about 2 ms, and target
checkpoint capture about 1–1.6 ms. Recursive snapshot averaged about 0.423 ms in
the earlier diagnostic probe. That probe's 9.877 ms restore included exhaustive
host readback; production restore time R has not been isolated and must not be
assumed zero. These observations are from different measurement modes, not one
matched throughput result.

For equal target stages S and a circulating window W, an optimistic all-hit bound
on token interval is at least `max(S, 4*S/W)`, before draft, checkpoints, IPC and
misses. W=3 allows at most three simultaneous target rows; W=4 can fill four stages.
For a drained burst of B rows, the ideal target-only interval is
`(4+B-1)*S/B`; refill draft cost is additional. With S=9 ms, B=3 costs 18 ms/token
for target work alone. If each burst needs three canonical 2 ms draft steps, one
extra 2 ms recursive step, 0.4 ms draft capture and restore R, the optimistic
interval is already `20.8 + R/3` ms/token, **before** target captures, misses or
IPC. That upper bound makes burst throughput an unattractive optimization target.

A rolling depth-two design that recomputes a two-token proposal batch on every
true pair instead adds roughly two draft passes per accepted token at stage zero.
With S=9 ms and an illustrative 1.3 ms target capture, its first-stage service
bound is approximately `9 + 4 + 0.4 + R + 1.3 = 14.7 + R` ms/token. The window
circulation lower bound is 12 ms/token, so stage-zero draft work may dominate.
Depth three adds another draft pass and another checkpoint slot; full target
occupancy alone does not establish an improvement. These equations assume all
hits and no recovery and are ceilings, not forecasts or benchmark claims.

Choose layer boundaries using measured stage service including draft/capture
work. Record miss depth, discarded stages/rows, all capture/restore bytes and
latency, canonical catch-up, recursive work, IPC, fill/drain and token intervals.
Only a matched live suite with exact target and draft state can determine whether
rolling depth two beats the current fast two-card path.

## CPU model and remaining gates

[test_wavefront_ring.py](test_wavefront_ring.py) passes seven tests including
capacities 1/2/3, each miss depth, first/nonfirst stages, full suffix discard,
31/32/33 extent and parity restoration, acceptance without physical rewinding,
wrong parents/generations/tickets, EOS and sticky failure. The model intentionally
uses deterministic synthetic state, not target arithmetic. It does not replace
real checked-copy tests, distributed delayed-reply tests, or GPU parity.

Next implementation gates: checked ring storage and native per-row candidates;
versioned lineage/slot protocol; forced rejection at every depth with strict
whole-model state; explicit operator ownership and interleaved canonical draft
parity; live recursive true-pair proposals; then matched, diagnostics-off timing.
No active runtime, controller, hardware setting or model artifact was changed by
this design work.
