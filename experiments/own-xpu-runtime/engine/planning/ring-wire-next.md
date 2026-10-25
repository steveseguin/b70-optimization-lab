# Proposed continuous depth-two wire and proposal contract

Design only, 2026-10-25. No active native source or controller imports this file or
[ring_contract.py](ring_contract.py). The persistent full-snapshot proof remains
frozen. Preserve commands 20–23 and the proven single-pending-row runtime default.
This proposal needs independent review and exact native qualification before use.

## Admission and work records

A new explicit ring mode requires the qualified target/draft partition on the
provider stage, max three global positions, and at most two unresolved tentative
rows per early stage. One native command executes at a time per owner. The final
stage remains verified-only with one unresolved verified candidate. Stage zero
may hold two completed tentative rows while downstream stages verify their inputs.

Require `--retain-steps none` initially. Existing HALF physically advances position
and swaps stage-zero banks, then builds a Candidate; existing `publish` writes
retained layer evidence, not the model's state transition. In ring mode create a
fresh Candidate for each physical ROW and retain it with that row's ticket. Do
not clear another row's Candidate, replay publish against live overwritten
streams, or rewind device position when accepting an older row. With retained
steps disabled, layer snapshots are absent and publish has no per-row file effect.
Reject unsupported callback/head-split/canary/legacy redo paths as in the current
wavefront admission, rather than silently combining ownership protocols.

Each record owns request epoch, global row ID, parent global row ID, exact prefix
digests, local ROW wire ticket, position, token, fixture, tentative flag, immutable
output bytes, Candidate and checkpoint slot. Global row IDs are coordinator IDs;
local wire sequences differ across stages because draft/control commands consume
sequences. Never interchange them.

## Proposed commands

| Op | Name | Request / effect |
|---|---|---|
| 24 | RING_ROW | Existing token/position/fixture fields; speculative0/1; fresh socket sequence. Checked shared RowMeta supplies global lineage. Execute at physical cursor, capture a free slot before tentative work, publish output bytes and keep the completed record unresolved. |
| 25 | RING_ACCEPT | `speculative` is original ROW wire ticket, other row fields exact. Resolve only oldest record after target verification. Release its slot and advance logical cursor; no model-state write or physical rewind. Final acceptance publishes verified output and raw hidden through the existing live handoff. |
| 26 | RING_ABORT_SUFFIX | Exact oldest rejected ROW identity. After drain, restore its checkpoint once, discard all later records/publications, advance branch generation and report every discarded global ID. Never clear sticky errors. |
| 27 | DRAFT_BATCH | Canonical true-pair step plus one recursive lookahead; `position/token` retain op23 meaning, `fixture` requests draft head0/1, `speculative=2` explicitly requests depth two. Return a bounded proposal batch only after recursive state restore completes. |

Commands 23 and 27 may interleave with **completed tentative** pending target
records only under the new ring mode and explicit partition. The owner must be
drained, with no outstanding kernel/publication callback or verified candidate
awaiting publication. No simultaneous queue submission is needed. Without that
mode, command23 retains its current empty-checkpoint requirement. Initial ring
proofs can restrict to command27; one-step command23 remains useful when only one
proposal fits before context/response end.

## Concrete metadata transport proposal

Keep the existing 32-byte Request and 64-byte Reply ABI, stage/final reserved
fields, exact negotiated F32 stream extent and 65,536-byte slots. Metadata uses
previously unused bytes below the existing reverse hidden slot; no offsets depend
on model hidden width.

- RowMeta: offset `2*SLOT+1024`, 224 bytes.
- ProposalMeta: offset `2*SLOT+1536`, 192 bytes.
- ResolutionAck: offset `2*SLOT+2048`, 128 bytes.
- Existing canonical true-pair header remains `2*SLOT+512`, 112 bytes.
- Existing final raw hidden remains `2*SLOT+4096`, up to SLOT bytes.

RowMeta little-endian format: `<4I3Q10i32s32s32s32s16x`.

The four unsigned words are magic `0x52494e47`, version1, size224 and flags
(tentative bit0, native-publication bit1; other bits zero). The three uint64s are
request epoch, global row ID and parent global row ID. The ten int32s are position,
token, fixture, owner stage, final flag, source stage, source ROW ticket,
publication ticket, payload byte count and dtype code1 (F32). The four digests
are request identity, prefix-before, prefix-after and payload SHA256.

For a request, publication ticket is zero. Stage-zero input has zero payload,
source stage -1 and source ticket0; its embedding input is the request token.
Other stages require exactly the full negotiated stream bytes from their preceding
stage, the recorded upstream ROW ticket and matching row/parent/prefix identities.
The root copies the entire upstream reply first, then constructs the next stage's
metadata with that source identity. Native ROW publication sets the publication
flag/ticket to its own reply sequence and hashes its full output payload. Owner
stage is always the process handling/publishing that header. Final ROW has no
boundary payload; its proposed target token is still not emitted until ACCEPT.
Resolution requests carry the retained row lineage and zero payload; they do not
pretend to transfer a stage stream.

ResolutionAck format: `<4I4Q8i48x`. Unsigned words: magic `0x5241434b`, version1,
size128, flags (bit0 means full restore-byte check performed). uint64s: epoch,
resolved global row ID, discarded row ID0 and discarded row ID1. int32s: owner
stage, reply sequence, original ROW ticket, physical position, committed position,
discard count, remaining pending count and sticky error. ACCEPT has discard count0;
ABORT_SUFFIX has count1 or2 and returns the exact suffix IDs. A successful abort
must report physical==committed==oldest rejected position and pending count0.
No unexecuted descendant gets a fabricated checkpoint. Final ACCEPT also preserves
the existing live hidden handoff/Reply bytes/token contract.

ProposalMeta format: `<4I6Q8i32s32s32s`. Unsigned words: magic `0x44525032`, version1,
size192, flags (head requested, restored). uint64s: epoch, batch wire ticket,
canonical seed row ID, parent row ID that supplied final hidden, final COMMIT wire
sequence, canonical provider step serial. int32s: seed input position, restored
canonical draft position, requested depth, available depth, guess0, guess1, sticky
error and restoration-complete flag. Digests: request identity, verified seed
prefix digest and exact raw hidden SHA256. Head-off prompt priming publishes no
guesses; context-end censoring can publish one, with unavailable token fields -1.
Requested/available depths are explicit; no silent fallback masquerades as depth2.

These layouts are proposed, not shipped wire support. Before native integration,
add struct-size/static-offset assertions and real socket tests for truncation,
mutation, stale slots, request epoch and exact payload hashing.

## Prefix identity and immutable issued work

Request identity binds model/profile, request/prompt identity and sampler mode.
The CPU prototype derives its initial digest from that identity and request epoch,
then folds each input token at its absolute position using a domain-separated
SHA256 chain. The native/coordinator implementations must use identical byte
encoding. Request epoch advances at quiescent RESET; global wire sequences never
reset. A row's prefix-before must equal its actual predecessor's prefix-after.
Corrected work reusing an absolute position receives a fresh row ID and branch
identity, so delayed old publications cannot be reused.

A proposal batch is seeded only by a verified true prefix. Guess d2 is explicitly
conditioned on d1 and cannot be admitted under a different parent token. Recursive
passes restore private draft device/pinned bytes, position, attention extent,
prepared command references and publication metadata before returning proposals.
Canonical true-pair advancement is retained; hypothetical recursive advancement
is discarded even when all guessed tokens later match.

**A newer proposal is not a verification event.** Suppose a recursive batch
produces `[7,9]`; both rows are already issued. The target confirms7, then a fresh
canonical step proposes8 instead of the in-flight9. Keep the issued9 ticket and
its work until the target output decides it. If9 is correct, accept it. If8 is
correct, reject9 and every descendant. A new batch's child of8 cannot be attached
to the issued parent9. Newer batches may replace only choices that have not been
issued, and only if their full parent prefix matches the actual branch.

[ring_contract.py](ring_contract.py) implements this CPU publication/selection
rule with immutable Issued records, bounded batch cache, request/epoch/seed
checks, exact parent digest and global parent-row checks, and target-only truth
updates. It also rejects an apparently matching later guess after an earlier
parent miss. It is a contract model, not a replacement for the coordinator's
stage ownership, stream slots or native state manager.

## Native/controller integration boundaries

The target ring uses one inventory/table manager with two preallocated snapshot
slots, not two independent StageCheckpoint instances. Each slot saves full target
scratch/KV/control and host bank/extent/history metadata. Independent draft state
is excluded only through the qualified operator partition and remains newer after
target abort. Canonical draft steps are synchronous scoped borrowers of the shared
submission owner; target error/failure flags and cumulative evidence are never
rolled back.

The coordinator tracks both the global verified frontier and stage-local physical
and logical cursors. Prioritize final ACCEPT and oldest row resolutions. Continue
pumping other sockets while stage zero computes a draft batch; the current blocking
op23 exchange should become an ordinary asynchronous queued command in this mode.
Copy every reply's complete payload before any owner can overwrite its slot.
On the first target mismatch, freeze descendant admission, drain outstanding ROW
commands, issue one suffix abort at each affected stage, discard stale publications,
and await all abort acknowledgments before admitting the corrected row.

EOS, length cap and RESET use the same suffix-drain discipline. DUMP/FINISH require
zero live slots and canonical physical/logical cursors. Attest the pending-ticket
inventory, discard identities, per-slot ownership and independent draft seal;
do not relabel a live speculative state as target-only or reuse v1 quiescence
claims without explicit ring fields.

## Proof sequence

1. Extend the CPU coordinator with row/parent/prefix identity and two pending rows;
   delay/reorder owner replies, reject every depth, and exercise EOS/reset boundaries.
2. Native scripted forced-miss ring proof: every target buffer and every accepted
   prefix exact, one restore per rejected suffix, no rewind on earlier acceptance.
3. Canonical draft advancement between target capture/abort: full target restore
   plus unchanged newer draft bytes/metadata, including capacity transitions.
4. Actual recursive batches: match legacy diagnostic true-pair proposals and
   canonical draft state after accepted/rejected branches; prove competing fresh
   proposals do not rewrite issued work.
5. Persistent matched live suite, diagnostics off, with source/model/topology/
   sampler identity and per-stage draft/copy/waste accounting. No speed claim from
   scripted guesses or a short proof.

Six prototype tests pass in [test_ring_contract.py](test_ring_contract.py), covering
fresh canonical disagreement, unissued replacement, both miss depths, stale/wrong
request/epoch/seed/restore/ticket/parent, and censored one-token availability. The
separate [ring ledger tests](test_wavefront_ring.py) cover physical versus logical
state, suffix restoration, banks/extents and sticky failure. Neither is GPU proof.
