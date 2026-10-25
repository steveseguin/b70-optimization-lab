# Live depth-one proposals for the wavefront pipeline

This opt-in path reuses the existing `mtp36::DraftRuntime::compute` arithmetic.
It does not train a draft, use scripted guesses, or commit recursively generated
hidden states. Native and CPU plumbing are implemented; GPU token/state parity
and useful throughput require separate qualification.

All stages take `--pipeline-wavefront --pipeline-live-draft`; only stage zero
takes `--mtp`, with `--draft-rank 0`. Existing two-card service and target-only
pipeline defaults are unchanged. Diagnostic depth-probe environment variables
are refused in this mode, even when set to zero. The first live path is depth one;
recursive depth two/three remains a later change after one-step qualification.

## True-pair handoff

The final stage copies the complete raw F32 final-layer `streams` at the final
layer boundary, before the final head transforms them. Only its successful
COMMIT publishes a usable handoff. Current geometry is negotiated via READY;
no model hidden width is encoded in this protocol. All byte counts are bounded
by the existing 65,536-byte slot.

`pipeline/live_draft.hpp` and `planning/live_draft.py` define the shared ABI:

- final map raw hidden: `2 * SLOT + 4096`;
- final map header: `2 * SLOT + 512`, exactly 112 bytes;
- first-stage input hidden: `SLOT`;
- first-stage input header: the same header offset, unchanged;
- header `<12i64s`: magic `0x4d545031`, version 1, stream bytes, hidden position,
  final stage ID, stage count, original ROW ticket, COMMIT sequence, input token,
  target next token, target head flag, reserved zero, ASCII SHA256 of raw hidden.

Final COMMIT replies contain the exact stream byte count and target next token
(or -1 if its head was skipped). The controller copies the header and full raw
bytes before issuing another final-stage command. It binds the copy to that
COMMIT's ticket, sequence, position, input token, output and stage identity.
Only verified target output or an actual prompt token may supply the next input.

Stage-zero command 23 runs one canonical draft step. `position=p+1`, `token` is
that verified input, `fixture` independently requests draft head 0/1,
`speculative=0`, and the normal command sequence/stage identity remain mandatory.
Its reply has zero stream bytes and a proposal for position `p+2` (or -1 with
head off). For a prompt of length P the draft head is enabled when `p+2 >= P`:
the final prompt **pair** can request a draft head even when its parent target
row's header reports head off. The first pair uses hidden row zero with input
one; the canonical draft starts at position zero and advances exactly once.
Do not create an extra terminal pair after EOS or the generation cap.

## Ownership and complete evidence

Command 23 requires no pending target row or active target checkpoint, no async
draft publication, and a contiguous canonical draft position. It authenticates
the owned hidden bytes, final ticket identity and confirmed token. A provider
error halts the live owner instead of returning a usable proposal.

The provider is constructed before the checkpoint inventory. All its mutable
device allocations are included in target checkpoint captures. Its two explicit
pinned transport allocations are also copied and byte checked through host
copies; unknown pinned allocations are refused. No draft step may run while a
target checkpoint is active, so rollback cannot erase a newer canonical draft
step or require restoring draft host metadata. This conservative initial design
copies some bytes unnecessarily; optimizing that ownership partition requires
its own proof.

At DUMP, stage zero writes `state-MARKER.draft`, using the existing sealed
four-file state bundle. FINISH writes `draft-final-state-sealed` independently.
`ownrt.draft-state.v1` includes every mutable draft buffer, private scratch,
pinned transports, exact layouts and meaningful host metadata. Compare a
sequential true-pair baseline and live overlap with identical prompt, output,
head mask, arithmetic/weights and terminal policy. Both target state and draft
state must match; token agreement alone is insufficient.

CPU checks cover the shared ABI, owned bytes and SHA256, stale/skipped/duplicate
pairs, wrong confirmed tokens, prompt bootstrap head selection, and the actual
checkpoint implementation restoring pinned bytes alongside device, KV, scratch,
metadata and output-slot bytes. See `test_live_draft.py`, `test_live_draft.cpp`
and `test_wavefront_checkpoint.cpp`. The controller's socket tests separately
exercise real framing and 2/4/6-stage event scheduling. No CPU test establishes
GPU arithmetic parity or a speed improvement.

Measured recursive-probe draft passes were about 2 ms each, but that diagnostic
measurement is not live throughput. Draft work competes with stage zero while
other stages can progress. Measure end-to-end decode, canonical draft step time,
idle time, target restore cost and misses on the same full suite before claiming
that the four-card live path is faster.
