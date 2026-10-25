# Rolling actual depth-two provider: isolated coordinator design

This directory is a CPU design model. No active scheduler, controller, native
source or current proof imports it. No GPU/build action is performed. Existing
MTP weights supply proposals; no training is proposed. The current quiescent
actual-provider gate must pass before any pending-target borrowing is admitted.

## Semantic owner and transport contract

For canonical seed input `S` at position `p`, the final committed parent is the
row at `p-1`. Stage zero must execute and ACCEPT `S` before op27, so native
`ring.last_accepted()` is an independent local seed identity. The final peer's
read-only record supplies the independently committed parent and hidden bytes.
Canonical provider state advances from `p-1` to `p` exactly once, captures its
post-canonical state, executes one hypothetical recursive step, and restores to
`p`. Its result supplies guesses for inputs `p+1` and `p+2`. The provider never
advances target truth, and a later target rollback must not erase that canonical
provider advancement.

The rolling controller may call op27 with zero, one or two already completed
**tentative** target rows pending on stage zero, provided the provider/target
ownership partition has separately passed that gate. Stage zero has one command
in flight and one in-order native queue. Other owners can continue running and
returning replies while op27 runs; the controller must keep servicing every
socket and the passive guard. There is no concurrent target compute on stage
zero during its provider operation.

A seed can itself have been issued tentatively and subsequently verified and
ACCEPTed. Preserve that original ROW tentative bit in its immutable metadata;
current verification comes from the accepted journal, not from clearing the
original bit. The current quiescent `ring_live_wire.seed_metadata` deliberately
rejects tentative seeds. A future rolling codec must admit this accepted case
under the new mode without weakening the existing quiescent codec's check.

Wire sequence allocation remains inside the generic
[ring Coordinator](../ring_coordinator.py). A future `reserve_auxiliary(27, seed)`
hook must reserve the next stage-zero sequence and set its busy command exactly
as ROW/ACCEPT/ABORT do. Provider completion retires that exact command only after
codec validation. It must not modify target physical/committed/pending cursors.
A separate provider wire counter, reserving after Popen/send, or decrementing a
wire sequence on cancellation is invalid.

## Two explicit scheduling fences

| Fence | Blocks | Allows | Release |
|---|---|---|---|
| Final parent record | Next final-stage ROW, which invalidates the record marker | Other owners' ROW/ACCEPT and all suffix drain/ABORT work | Full validated op27 reply in the first rolling version |
| Next canonical provider seed | Stage-zero ACCEPT beyond the next provider seed; later verified stage-zero ROW after that seed is accepted | Up to two tentative child ROWs, other owners, target suffix drain | Provider completes that seed exactly once |

The second fence prevents prompt lookahead or multiple local accepts from moving
native `last_accepted()` beyond the provider's required next seed. Tentative
children remain allowed because they do not advance that accepted journal.

The final-record lease is **not** an outstanding native command. Do not put a
fake busy command into the Coordinator's stage array: a target miss needs to
drain and abort its suffix before creating the corrected canonical seed, and a
fake busy final stage would deadlock that drain. Implement a pre-reservation ROW
admission hook instead. The hook suppresses only the final ROW that would
invalidate the retained parent; it does not suppress other owners or ABORTs.

The current op27 protocol has one reply after capture, recursive work and
restoration. Although the native peer copies the parent near command start,
Python cannot observe that point. Therefore the first rolling version must hold
the final lease until the full reply. Releasing it after socket send or inferred
elapsed time is unsafe. A future early-capture acknowledgment would require a
new versioned event containing request/epoch/seed/parent/command/commit/hidden
identity, explicit native ownership of copied bytes and an independent protocol
qualification. It is not part of this first design.

## Integration with actual proposal provenance

On provider reply, first validate the exact wire owner, request, epoch, immutable
seed/parent, parent final commit, provider serial, hidden SHA, restored position,
available depth and vocabulary using the real codec. Then confirm stage zero's
physical/logical cursors and pending row IDs equal its reservation snapshot.
Retire the auxiliary command and publish a `ProposalBatch` with:

- batch ticket = the op27 wire sequence;
- seed length = `p+1`, seed digest = the accepted seed's `after` digest;
- restored position = `p`, restored = true;
- tokens = the one/two actual guesses, never reference tokens.

Use the existing `Proposals.issue/choose/verify` rules. A fresh canonical d1 may
disagree with an older recursively issued d2 for the same position. Keep the
already issued row ID, token, original ticket and parent prefix immutable. New
batches can guide only unissued work. The target's eventual verification chooses
acceptance or a drained suffix rollback. Never overwrite issued work to make a
newer guess appear to have been used.

An auxiliary command cannot be admitted during mismatch drain, suffix abort,
EOS/cap drain or reset. If a stop arrives during op27, admit no further target
rows, wait for its normal reply only while the owner remains healthy, and retain
failure evidence. A fault or invalid reply closes admission; do not submit
recovery work or retry the provider. EOS/cap needs no provider step for the
unconsumed token after the final output. Reset must wait for both target commands
and provider command/record leases to drain before a separately admitted epoch
change; this prototype grants no native RESET support.

## Qualification order

1. Finish the current quiescent actual-provider gate: 117 true pairs, 32 actual
   d1/d2 comparisons, canonical 73-buffer parity and private full restore checks.
2. Run the
   [pending-target forced-rollback gate](../../../../../notes/2026-10-25-ring-pending-provider-gate.md):
   locally ACCEPT seed `p`; complete two tentative children; op27 advances the
   provider; actual target verification rejects the first child; one suffix
   ABORT discards both. Before any provider replay, compare all canonical
   71 device + two pinned buffers, full provider host/Sequence identity and
   private image before/after the target abort. Compare full target restore too.
   Suggested seeds 95 and 96 exercise target and recursive-provider extent
   boundaries respectively. Save the seed output before later ROWs overwrite
   stage-zero's output slot. Scripted wrong target children here force proof
   coverage only; this is not a speed benchmark.
3. Add a one-pending-row variant: accept a correct first child, borrow the next
   canonical seed, reject the second child, and preserve newer canonical state.
4. Integrate generic Coordinator auxiliary reservations and the two admission
   hooks in a new opt-in rolling controller. CPU tests must reorder target and
   provider replies, delay each owner, inject wrong identities and prove progress
   through misses, final-record leases and stop drains on 2/4/6 stages.
5. Only after actual rolling state/output parity, measure the unchanged 12-prompt
   cold suite and report its decode metric separately from full response/TTFT.
   Current quiescent or scripted timings cannot establish rolling throughput.

## Isolated prototype and limits

[arbiter.py](arbiter.py) models the two fences, canonical seed progression,
authoritative auxiliary reservation, immutable parent lease, target cursor
preservation and failure latch. It consumes the existing generic Row/Command and
ProposalBatch types. It does not copy or modify the core scheduler and does not
claim that its proposed hooks already exist. The codec and complete state proof
remain external prerequisites.

The six CPU tests cover 2/4/6 owner admission, no premature final overwrite,
other-owner progress eligibility during op27, prevention of local seed overshoot,
no phantom busy final command during a miss, exact sequence/serial/cursor refusal,
and the real `Proposals` behavior when new d1 disagrees with an issued older d2.
Early EOS releases the unneeded parent lease without advancing a provider seed.
They model event eligibility, not GPU timing or full end-to-end rolling progress.

```sh
PYTHONPATH=engine/planning python3 -m unittest discover \
  -s engine/planning/rolling-provider-next -p 'test_*.py' -q
```
