# Opt-in target-only ring qualification

The native implementation in `../src/pipeline/ring/` promotes the reviewed
control and checked-copy proposal from `ring-native-next/`. It is a correctness
qualification path, with scripted guesses supplied by the controller. It does
not enable recursive MTP, provider interleaving, persistent RESET, or a new
serving default. The existing operations 20–23 remain unchanged.

Admission requires `--pipeline-ring`, an explicit lowercase
`--pipeline-ring-request-sha256`, retained steps `none`, and the existing scalar
resident F32 pipeline configuration. It refuses wavefront, MTP, live drafting,
provider partition and persistent requests. Initial epoch is zero. Optional
`--pipeline-ring-verify-restore` compares every restored target byte;
`--pipeline-ring-trace-limit` bounds command evidence to 0–100000 rows.

Operations 24, 25 and 26 execute a row, accept the oldest completed row and reject
an entire unresolved suffix. The outer loop retains contiguous command sequence
checks and explicit stage/final identities. Control metadata preserves the
original tentative bit and original ROW ticket. A verified final stage admits
one pending row; earlier stages may retain two completed tentative rows.
Accepting an older row changes only the logical committed cursor. Rejecting a
suffix restores its oldest snapshot once and retires both slots before any
corrected input can execute.

Both checkpoint slots share one allocation census. Their images and four checked
copy tables are allocated before the census freezes. Complete target mutable
buffers, bank metadata, attention extents, host history/cache metadata and output
bytes are captured. Inactive legacy snapshot storage is explicitly enumerated as
runtime-private. The initial executable ring refuses a draft provider, even
though the isolated transport tests also cover independently owned draft bytes.

The dispatcher copies input into owned host storage, validates its full SHA256,
and uploads those exact bytes through the existing prepared-input HALF path.
The native model executor and arithmetic are shared. CPU compilation is not
proof of model parity for this preparation path: the required device gate is a
matched scripted two-slot run with exact full-state comparison and forced first-
and second-proposal rejection, including an older ACCEPT after a newer row has
physically executed.

DUMP produces `state-MARKER.ring-state.json`, with schema
`ownrt.ring-state.v1`, bound to the exact state seal and
`ring-checkpoint-layout.json`. It requires no pending rows or slots, physical and
logical positions equal, canonical bank parity, zero sticky error, and conserved
row/capture/release/restore counters. FINISH writes a separate fresh
`ring-quiescence.json`; it cannot overwrite a sealed DUMP attestation. Initial
stage metadata uses `verified-ring`; historical target-only and wavefront
attestations cannot establish ring qualification.

CPU checks are `test_native_ring_control.cpp`, `test_native_ring_wire.cpp`, and
`test_native_ring_checkpoint.cpp`. The last includes the actual main parser,
checked Host Device/CopyEngine/SnapshotFlat transport and the full dispatcher
compile. It executes no model kernels and opens no GPU. The durable CPU receipt
and exact patch are in `evidence/native-ring-cpu.json` and
`evidence/native-ring.patch`. A matched device state proof remains an open gate.
