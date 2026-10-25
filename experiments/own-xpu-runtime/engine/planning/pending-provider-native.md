# Pending-provider rollback qualification

This opt-in gate extends ring-live command 27 to a completed tentative target
suffix of one or two rows. It is a correctness qualification, not a speed mode.
The canonical provider still advances once per accepted true input pair. No new
model arithmetic, target guesses, or training are introduced by the native gate.

All owners require `--pipeline-ring-pending-provider` and
`--pipeline-ring-verify-restore`; the first owner additionally requires
`--pipeline-ring-verify-provider-survival`. Existing quiescent ring-live and
commands 20–26 retain their original defaults. The pending mode still refuses
RESET and incomplete or verified-but-unaccepted target work.

Before each target suffix ABORT, the first owner records all canonical provider
device/pinned bytes, the separate recursive image, current and saved provider
host state, saved target metadata, saved pinned contents/row descriptors,
provider-owned counters, full Sequence identity, and exposed typed prepared
bindings. The target rollback then runs once. Immediate native comparison of the
same state must pass before an ACK or success receipt can be published. Target
snapshots exclude the exact validated provider canonical and private inventories.

Prepared descriptors are encoded field by field: Spec/Geometry/site values,
allocation IDs, pointers, argument and operation bytes, command/submit ownership,
and descriptor generation. Opaque std::function storage and C++ padding are not
serialized. Shared Engine timing/submission totals and Device copy-counter
values are explicitly excluded because target restoration changes them; their
stable ownership addresses are checked. Provider-owned counters and recorded
result timings must remain exact.

`ring-provider-survival.jsonl` contains bounded
`ownrt.provider-abort-survival.v1` records. Each binds the exact abort sequence,
oldest row and discarded suffix IDs, provider position/serial at each target
capture, before/after payload text and SHA-256, compared allocation identities,
and independently checked byte/host/Sequence/prepared-binding equality. The
payload schema is `ownrt.provider-survival-state.v1`. Allocation hashes support
audit; the native success decision compares actual full byte vectors.

Final attestation uses `ownrt.ring-state.pending-provider.v1`, mode
`verified-ring-pending-provider`, and `provider_borrow_mode: pending-target`.
It binds the survival stream SHA, successful check counters, pending-depth
histogram, target and provider sealed state, and the unchanged explicit live
checkpoint inventory. Quiescent v4 evidence retains its original schema and
zero-tentative restrictions. State comparison for this gate requires a separate
v5 manifest; it cannot be relabeled as a quiescent proof.

The controller chooses positions; the native code has no q95/q96 constants.
The proposed model replay crosses an attention extent boundary, exercises a
two-row rejection and an older ACCEPT followed by a one-row rejection, and
checks exact final target and canonical draft state against the retained
quiescent reference. CPU tests only qualify ownership/control and synthetic
storage behavior. Model arithmetic and actual provider rebindings require that
separate parent-owned GPU replay.
