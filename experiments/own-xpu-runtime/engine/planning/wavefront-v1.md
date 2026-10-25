# Bounded stage speculation protocol v1

Implementation record, 2026-10-25. Opt-in correctness foundation for actual token
work overlapping across stage owners. It does not enable live MTP proposals,
train a draft, change kernel arithmetic or qualify a speed result. The ordinary
two-card controller and target-only pipeline protocol remain unchanged.

## Native interface

Use `--pipeline-wavefront` with the existing explicit pipeline boundaries/stage,
resident one-card-per-process F32 GSQ mode. MTP, TP and batched prefill are still
refused in this first stage protocol. `--pipeline-wavefront-verify-restore` enables
complete byte comparison after each aborted row; `--pipeline-wavefront-verify` is
an alias. Trace records default to 4096, controlled by
`--pipeline-wavefront-trace-limit 0..100000`. Counters continue after the trace cap.

The existing little-endian 32-byte request / 64-byte reply ABI is retained.
Request `reserved[0:2]` still contains stage index and final-stage boolean.
Socket command sequence is strictly increasing and is the unique row ticket;
RESET/new-request commands are unavailable in this mode.

| Operation | Request fields | Meaning |
|---|---|---|
| 20 WAVE_ROW | token, position, fixture; speculative=0 or 1 | Execute verified or tentative input. The command sequence becomes its ticket. |
| 21 WAVE_COMMIT | same token/position/fixture; speculative=original row ticket | Commit exactly that pending row after coordinator verification. |
| 22 WAVE_ABORT | same token/position/fixture; speculative=original row ticket | Restore exactly that tentative row. Verified rows cannot be aborted. |
| 4 DUMP | position=dump marker; speculative=0 | Requires no pending row or active checkpoint; writes sealed target state and a bound attestation. |
| 5 FINISH | speculative=0 | Requires no pending row or active checkpoint, then cooperatively exits. |

Each owner has at most one unresolved row. The coordinator admits at most two
positions ahead of the final committed frontier: verified row n can run downstream
while guessed row n+1 runs earlier. Verified rows may commit on earlier stages
immediately because their input token is known. A tentative row remains pending
until the final target verifies its input or rejects it. Stage output streams must
be copied into coordinator-owned immutable bytes before the producer can reuse its
output slot. Only ROW replies contain meaningful output token/stream fields.

The final stage refuses tentative input and requires each decoded input token to
match its previously committed target output. Prompt rows use fixture0; the last
prompt row uses fixture1 and starts head evaluation. Subsequent fixtures increment
exactly once. Only a final COMMIT reply authorizes output emission. A mismatch
invalidates the complete dependent tentative suffix; drain or cooperatively finish
its current work, then ABORT before corrected admission. EOS and length caps also
resolve every tentative row before DUMP/FINISH. There is no retry or implicit reset.

## Checkpoint implementation and limits

[wavefront.hpp](../src/pipeline/wavefront.hpp) is the pure ticket/causality ledger.
[checkpoint.hpp](../src/pipeline/checkpoint.hpp) implements `StageCheckpointFor`,
instantiated on the production Engine. It uses the existing checked CopyEngine
admission and SnapshotFlat tile copy kernel. Both copy directions are validated
at load; fixed descriptor tables are prepared once.

The first proof copies every complete live mutable physical device allocation,
including active/spare/reserve banks, KV, scratch and controls. It excludes weight
allocations and precisely named unused private storage of the preserved legacy
snapshot controller. New private backup/tables are separate allocations. The
complete checkpoint is capped at512MiB and still subject to the engine's30GiB
per-card arena budget. This deliberate complete-image implementation may cost
more than the existing optimized single-rank snapshot. Omission/bank optimizations
require their own proof later.

Capture also retains host history, lookup IDs, selected/loaded-layer metadata,
FP32 source metadata, bank identity/parity, both prepared attention extents, and
the owner's first65536-byte shared output slot. Callbacks and submission observers
must be quiescent. Abort restores bank ownership and prepared extents, all captured
bytes and host metadata. It checks sticky error/poison before restoration; errors
are never erased. Verification mode compares every restored allocation byte to
its private backup and checks the restored output slot. Allocation additions,
released/replaced storage, nested checkpoints and stale resolution tickets fail.

The legacy HALF implementation is called internally with its speculation flag
clear: the independent stage checkpoint owns this rollback. Consequently legacy
HALF timing rows label those calls non-speculative; use `wavefront.jsonl` and its
ledger counters for the new tentative/commit/abort classification.

## State evidence and CPU qualification

Startup `pipeline-stage.json` explicitly records mode`wavefront` and
`speculation_enabled:true`. It is not target-only evidence. DUMP writes the normal
strict four-file `state-MARKER/` bundle, then sibling
`state-MARKER.wavefront-state.json`. The sibling is necessary because the bundle
reader rejects unexpected files within the sealed directory.

The attestation schema`ownrt.wavefront-state.v1` records mode`verified-wavefront`,
stage ID, dump marker, SHA256 of `state-seal.txt`, actual and committed position,
no pending ticket/checkpoint, abort and verified-restore counts, saved bytes,
bank parity, canonical active/inactive allocation mapping and inactive alternate
bank names. Native checks actual device position against the ledger, first-stage
bank parity against committed position, and complete snapshot accounting.
An existing dump attestation cannot be changed. FINISH writes only a separate
`wavefront-quiescence.json` and trace summary; it cannot modify dump-bound evidence.
The comparator must explicitly admit this quiescent verified mode and validate its
seal/position/restore proof. Existing target-only validation must not be weakened.

CPU sources and retained results:

- [test_wavefront.cpp](test_wavefront.cpp): 2/4/6-stage causal state histories,
  forced rejection at early/middle/late proposal indices, context-edge positions,
  stale/reused tickets, wrong tokens, final-stage and unresolved-boundary refusals.
- [test_wavefront_checkpoint.cpp](test_wavefront_checkpoint.cpp): actual checked
  Device/CopyEngine/SnapshotFlat on Host backend with a small injected owner;
  complete scratch/KV/bank bytes, attention extent and host metadata restoration,
  shared output, sticky error refusal, sealed attestation binding and immutability.
- [wavefront-cpu.json](evidence/wavefront-cpu.json) binds sources, binaries, commands
  and [ledger](evidence/wavefront-cpu-0.log)/[checkpoint](evidence/wavefront-cpu-1.log)
  logs. Two corrected fixture-only preparation failures are explicitly recorded.

These CPU tests do not establish native numerical parity, concurrent device-event
ordering, device checkpoint cost or live-draft speed. Required next gates remain:
forced-miss native state equality versus target-only, complete pending-work drain,
context-capacity edges, then measured scheduling/checkpoint cost and separately
qualified live recursive MTP. See [wavefront-next.md](wavefront-next.md).
