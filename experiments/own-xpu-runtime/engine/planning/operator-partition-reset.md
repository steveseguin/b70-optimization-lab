# Opt-in operator ownership and persistent cold requests

Implemented native scaffolding, 2026-10-25. The established full-owner snapshot
remains the default. CPU tests pass; GPU qualification must precede runtime or
throughput claims. These changes do not yet permit draft execution beside a
pending target row or implement the deeper checkpoint ring.

## Explicit target/draft ownership

`--pipeline-draft-partition` requires live draft mode. Stage zero records the
actual device allocation census before constructing DraftRuntime. The new
[pipeline/operator_state.hpp](../src/pipeline/operator_state.hpp) checks that all
new nonweight device allocations exactly equal the provider's declared mutable
IDs. Existing target IDs and provider IDs must be disjoint; missing, unknown,
duplicate or weight-as-mutable declarations fail admission. The two pinned draft
transports are supplied explicitly because Engine's device census excludes
pinned allocations. Category, extent, liveness and identity are checked separately.

[StageCheckpoint](../src/pipeline/checkpoint.hpp) then snapshots the complete
target-owned state and leaves independent draft bytes alone. Its frozen census
still checks every independent allocation's identity. Target cache metadata and
physical cached bytes stay together. Provider matrix/fused buffer lookup checks
membership in its mutable set; a draft step also verifies that target history,
lookup, selected/loaded state, FP32 cache identities/extents, target attention
extents and bank parity did not change. Submission remains synchronous and drained.

The default full-owner snapshot retains its `ownrt.wavefront-state.v1`
attestation. Partitioned stage zero instead emits
`ownrt.wavefront-state.partition.v1`, `checkpoint_scope:"target-owned"`,
`target_mutable_checkpoint_bytes`, a SHA256 binding to the checkpoint layout,
and at DUMP a SHA256 binding to the independently sealed canonical draft state.
The layout identifies target captures, independent draft allocations, inactive
legacy snapshot storage and this checkpoint's private backup/tables. It explicitly
sets `complete_mutable_physical_allocations:false` for partition mode.

This is the ownership prerequisite for continuous rolling speculation. Current
op23 admission still refuses a pending target checkpoint. Enabling interleaving
or a second pending row needs a separate protocol and GPU parity gate; see
[wavefront-ring-next.md](wavefront-ring-next.md).

## Persistent cold-request boundary

`--pipeline-persistent-requests` requires live wavefront mode. Command 11 is
admitted only at a quiescent boundary with zero token/position/fixture/speculative
payload and the existing exact stage/final identity. The global socket sequence
continues across requests. Per-request wavefront and draft sequence ledgers reset;
a new controller scheduler must start from each persistent owner's current wire
sequence, not zero.

The controller writes the original native output directory's
`reset-GLOBAL_SEQUENCE.txt` containing exactly two newline-terminated lines:
new output directory and unchanged oracle. The new directory must be fresh,
normalized, absolute and strictly beneath that original native directory. Metadata
is read once from a held regular single-link file with `O_NOFOLLOW|O_NONBLOCK`, an
8 KiB cap and stable identity checks. FIFO, extra lines, oversized input, outside
paths and dangling symlink destinations/ancestors are refused. Parsed values are
passed into the existing reset implementation; it does not reopen the pathname
on this opt-in path. Legacy callers retain their existing default behavior.

The [persistent wrapper](../src/pipeline/request_reset.hpp) checks both target
and draft failure state before zeroing, including the expected true-pair frontier.
It reuses existing cold reset for all device KV, scratch, active/spare banks,
lookup and history state, then resets both target attention extents and the draft
extent to 32. Physical allocation IDs are retained. FP32 source/extent fields
are validity metadata: clearing them does not free the preallocated FP32 buffers.

The old reset also zeroes private checkpoint device tables. Therefore the wrapper
rebuilds and uploads both checked descriptor tables before any subsequent ROW.
It clears checkpoint counters and stale output references, shared handoff slots,
provider publication flags, per-request ledgers and traces. It copies immutable
stage/plan/checkpoint layout sidecars into the new native request directory.
Per-request counters are cleared after all reconstruction and cold checks, so
reset maintenance is outside the next request's timings.

`wavefront-reset.json` contains schema `ownrt.pipeline-reset.v1`, stage ID,
global sequence, target position zero, draft position zero for the provider owner
(or null elsewhere), no pending ticket/error, preserved allocation IDs, both
attention extents, and counter/trace reset flags. With `--reset-dump none`, the
boundary produces bounded receipts and traces rather than full raw model dumps.
Explicit DUMP remains available for a separate two-request correctness proof;
normal suite collection needs only tokens/timings and its selected final dump.

## Validation and remaining gates

[operator-partition-reset-cpu.json](evidence/operator-partition-reset-cpu.json)
records the exact tested source/binary hashes and commands. The fixture uses the
actual checked CopyEngine/SnapshotFlat implementation and mirrors the real
Engine's device-only allocation registry. It captures target state, advances
synthetic independent draft device and pinned bytes, aborts target, and proves
that target bytes/metadata restore while newer draft bytes survive. It then
zeroes the copy tables as legacy reset does, rebuilds them, and proves a second
capture/restore. It also exercises partition/seal metadata and malformed reset
inputs. The established full-owner checkpoint fixture passes separately.

These are CPU ownership/transport tests with small synthetic buffers, not a
full-model reset or draft arithmetic proof. First run two identical cold prompts
on the same loaded owners with complete target and draft dumps after each,
partition disabled, and compare both with the accepted single-request reference.
Then qualify partition mode independently. Only after those gates should a
persistent multi-prompt benchmark use this boundary; no chain of fresh servers
or automatic retry is needed.
