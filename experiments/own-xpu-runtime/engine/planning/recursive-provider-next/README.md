# Isolated command 27 provider proposal

No active engine or controller imports this directory. The current scripted ring
proof remains target-only. This proposal reuses the existing trained MTP weights
and existing `DraftRuntime::live_step` and `compute(..., recursive=true)` paths;
it introduces no training or model arithmetic executor.

`batch.hpp` owns causal admission and the canonical/recursive transaction.
`draft_runtime_extension.inc` is an actual class-member extension for the existing
DraftRuntime, compiled through a temporary include overlay. `test_batch.cpp`
executes the generic transaction with synthetic provider storage. The tests do
not run the real model kernels; actual draft-state parity remains a device gate.

## Position and ownership contract

A parent final COMMIT belongs to input position p. Its raw final-layer hidden
state and the confirmed input token at p+1 advance canonical draft state once.
The seed row is that verified INPUT at p+1; its own target ROW or COMMIT need not
have executed. An immutable seed originally issued tentatively can keep that
historical flag after its token is verified. The boolean flag alone does not
establish verification.

ExpectedPair comes from the coordinator's retained verified-input identity and
independently retained parent final COMMIT, never from decoding the same incoming
payload twice. It binds the complete seed and 112-byte Handoff plus the next
provider serial. Native sequence admission also checks request/epoch, contiguous
canonical positions, exact seed ancestry/prefix, head mask, final input/output,
monotonic final commit, and complete owned raw-hidden SHA256. For the first seed,
the parent prefix is derived from request identity and the parent's input token.
The draft head mask equals `seed.fixture > 0`; it can be true while the parent's
target head mask is false near the end of prompt priming.

After `live_step`, d1 and canonical draft state are retained. Only then is a
checkpoint captured. One existing recursive `compute` predicts d2 from d1 and
its draft hidden stream. The hypothetical state is restored to the post-canonical
checkpoint before returning either proposal. No-head priming advances canonically
without a checkpoint. At capacity, d1 can remain available while d2 is censored.
A branch error or failed restoration poisons the transaction; no recovery copy or
partial proposal is published after a failure.

## Snapshot scope

The native extension enumerates the real mutable device inventory and both
provider-owned pinned allocations: publication is exactly 8 bytes/output_ring;
half-staging is exactly `4 + stream_bytes`/pinned_slab. Geometry comes from the
runtime, not an assumed allocation count. The current model has 73 canonical
allocations; the synthetic test exercises all 73, including the final pinned-like
rows, but this count is not hardcoded into native admission.

The host snapshot includes canonical position, attention extent, disabled and
async flags, pending-head/confirmed metadata, publication event and start time,
queued probe metadata, owned reverse-hidden bytes and captured-plan status.
Active callback or async ownership is refused BEFORE draining because drain can
invoke callbacks. Restored attention extents rebind existing prepared commands.
Target bank/history/lookup/selected-layer/FP32-cache metadata is checked unchanged,
and the prior profiling class is restored. Submission/timing/read counters are
cumulative evidence and are not model state.

Default operation performs the required device snapshot/restore and metadata
checks, without full byte readbacks. Qualification enables byte comparison of
every canonical device and pinned allocation against the post-canonical snapshot.
The existing compute path still performs its ordinary scalar error/token reads.
The provider retains capture/restore/verified-restore counters; Sequence exposes
the last successful result with snapshot bytes and verification status so a future
bounded command trace can bind those checks to the exact batch serial. A censored
or no-head batch is canonical without claiming a byte-verified restore.

The image is explicitly provider-private runtime storage, outside mutable_ids
and outside the canonical sealed draft dump. It must be allocated before owner
partition admission and target-ring census freezing. A separate validated private
inventory is REQUIRED at integration: hiding the image from Engine allocations,
adding it to canonical mutable_ids, or treating it as target-owned would each
break the ownership/parity contract.

## Proposed wire and integration gates

Existing operations 20–26 stay unchanged. Future operation 27 should receive the
immutable seed metadata, the parent Handoff and a complete owned raw-hidden
payload. Request token/position identify the confirmed seed; fixture carries the
requested draft head mask, not the parent's target head mask. Its 192-byte reply
is ProposalMeta with exact request/epoch/seed/parent/final-commit/provider-serial,
canonical restored position, seed prefix, raw-hidden digest and d1/d2 availability.
The caller validates every field against its retained records before issuing rows.
The proposal helper does not implement this socket adapter.

Required source integration, after the scripted ring gate:

1. Add an opt-in depth-two provider flag and include the helper outside the class
   and extension inside DraftRuntime. Prepare its private image before final
   ownership census. Preserve default two-card and existing live-step behavior.
2. Extend OperatorStatePartition with explicit provider-private device IDs. Require
   exact, disjoint classification of target mutable, canonical draft, pinned draft
   and private runtime IDs; include those roles in sealed inventory evidence.
3. Admit a synchronous op27 first at a quiescent target boundary. Preserve raw
   final hidden and complete final ticket identities before shared slots can be
   reused. Qualify d1 and all canonical draft bytes/host state against sequential
   live_step replay on identical true pairs and head masks.
4. Separately admit op27 while completed tentative target rows are pending only
   under the independent partition. No target command, callback, snapshot or
   suffix restore may run during the draft transaction. After it completes,
   target abort must leave the newer canonical draft state and its private image
   unchanged. Qualify that forced-rejection scenario before continuous overlap.
5. Keep recursive proposal ancestry immutable. A fresh canonical guess may differ
   from an already issued recursive guess without invalidating a correct parent;
   a wrong parent invalidates all its descendants. Require every discarded target
   suffix ACK before issuing corrected work.

## Validation

The lightweight test covers post-canonical restoration, 31/32/33 extent changes,
no-head/capacity censoring, no default full readbacks, independent identity
rebinding refusals, callback refusal before drain, and failure poisoning without
recovery. The overlay script creates a fresh temporary source tree containing
only the modified draft include, leaving canonical files untouched. A host-only
`-fsyntax-only` compile checks the actual extension against the current full Engine
and DraftRuntime definitions. It does not execute their kernels or initializer.

The CPU receipt, source hashes and exact proposal patch are stored beside these
files. These are implementation evidence, not measured rolling acceptance or a
throughput result.
