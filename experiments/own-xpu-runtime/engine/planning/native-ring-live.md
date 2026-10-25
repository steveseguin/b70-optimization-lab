# Quiescent ring-live depth-two gate

The opt-in `--pipeline-ring-live-draft` mode enables existing-MTP canonical plus
one recursive proposal through operation 27. It does not use either proposal for
target execution in this gate. Every target ROW must be verified and all stages
must be idle for the provider borrow. Target-only operations 24–26 and existing
operations 20–23 retain their defaults.

The flag implies existing internal live-provider and independent-partition
semantics. Only stage 0 receives `--draft-mtp`, an absolute
`--pipeline-ring-final-shared` path, and optionally
`--pipeline-ring-recursive-verify-restore`. The peer path is stored at startup;
it is opened read-only on the first operation 27, after all stages are ready.
Its regular-file size, descriptor and named inode remain pinned.

The final owner publishes a 360-byte FinalRecord at shared offset
`2 * 65536 + 2560`. It includes the committed parent RowMeta and existing raw
hidden Handoff. A release/acquire marker is invalidated before the next final
ROW and published after COMMIT. Stage 0 copies the independently owned record
and hidden bytes between matching marker reads, then checks all identities and
full hidden SHA256. No record is fabricated from the current relay payload.

The controller first executes and ACCEPTs the verified seed at stage 0. Native
operation 27 binds incoming seed metadata to StageRing's owned last-accepted row,
and the relay header/hidden bytes to the independently read final event. The
confirmed seed is position p+1 while the parent final event is position p. Only
after this borrow completes does the controller forward the seed downstream.

Canonical advancement uses the existing `live_step` exactly once. A private
snapshot is then taken; existing `compute(..., recursive=true)` predicts one
additional token and its hypothetical state is restored before publication.
The canonical draft dump still contains the same device and pinned allocations.
The recursive image is a separately admitted provider-private allocation, counted
in resident storage but excluded from canonical state. All target, canonical
provider, pinned provider and private IDs are classified exactly once.

Reply metadata is the 192-byte ProposalMeta at `2 * 65536 + 1536`; reply token is
d1 or -1, reply bytes is 192. No-head priming and context censoring are explicit.
The bounded `ring-draft-batches.jsonl` records identities, proposals, restoration
checks, and canonical/capture/recursive/restore milliseconds. CopyEngine currently
submits one checked copy per canonical device allocation each way, preserving the
qualified diagnostic mechanism as the first baseline. A flattened checked copy
path is a later measured optimization, not part of this gate.

DUMP produces the unchanged canonical draft bundle at `state-MARKER.draft`.
The new `ownrt.ring-state.live.v1` attestation and
`ownrt.ring-checkpoint-layout.live.v1` layout bind that seal and separately classify
the private image. They require quiescent-target borrowing, zero target speculative
work, exact provider position/serial, empty transactions, and conserved provider
capture/restore/verification counters. State-set v4 validation preserves earlier
v3 target-only ring semantics.

CPU checks include the actual full native translation unit and parser, native
readonly peer and operation-27 admission, the actual recursive member snapshot
code with checked Host Device/CopyEngine allocations, all 71 device and two pinned
allocations, unchanged target bytes/metadata, pending callback refusal before
drain, and failure poisoning without restoration after injected target mutation.
Arithmetic in that fixture is synthetic. The first real-model replay must still
compare all target state, all canonical draft state, and actual d1/d2 against the
retained reference before any proposal-driven target overlap is admitted.

See `evidence/native-ring-live-cpu.json`, its log, and the exact
`evidence/native-ring-live.patch`. The isolated design and its earlier syntax-only
proof remain in `recursive-provider-next/`. No training is involved.
