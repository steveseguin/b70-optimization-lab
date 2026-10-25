# Actual recursive provider: quiescent target gate

The new `tools/ring_live_driver.py` is a separate opt-in qualification controller.
It uses existing MTP weights and the existing native canonical/recursive compute
paths. It does not train a draft or feed any hypothetical guess into the target.
CPU tests exercise the wire and controller; native GPU/state qualification is a
separate gate owned by the run coordinator.

For each verified input, execute and ACCEPT its ROW on stage zero. For positions
one onward, call op27 using the previously committed final-stage parent before
forwarding the new input to later stages. All target owners have no outstanding
command or unresolved row during the provider call. The provider's canonical
step advances once; a private post-canonical checkpoint protects one hypothetical
recursive step and restores it before publication. Guesses are compared with
retained evidence and discarded. Prompt tokens and actual target outputs alone
supply target inputs. Native admission also refuses tentative target rows in
this first mode. Pending-target borrowing is a later qualification.

The final stage publishes a 360-byte committed record at `2*SLOT+2560`: a
24-byte header with release-published commit marker, immutable 224-byte RowMeta,
and 112-byte raw-hidden Handoff. Starting its next ROW invalidates the marker.
The controller owns a copy bound to the actual final ROW/ACCEPT tickets. Stage
zero separately opens the final shared file read-only, pins its inode, copies a
stable event and validates the raw-hidden SHA against that final-owned record.
The relayed controller header/payload must agree. This is independent of merely
re-reading controller-supplied input as its own authority.

The op27 request carries the locally ACCEPTed seed's global lineage and prefix,
token/position, exact head mask and requested depth two. Its 192-byte publication
binds request, epoch, seed/parent IDs, final commit, provider serial, original
command ticket, restored position, available guesses and parent hidden hash.
The first gate requires full recursive restoration verification. Private backup
storage is excluded from canonical draft state and target mutable state; its
inventory and verification counters require separate native attestation.

Use the ordinary full lab pipeline configuration and add:

```json
{
  "ring_live_draft": true,
  "use_proposals": false,
  "verify_recursive_restore": true,
  "recursive_reference": "/absolute/path/to/recursive-provider-reference-v2.json",
  "eos_token_ids": [248044, 248046]
}
```

The retained v2 reference covers 87 prompt tokens, 32 actual target outputs,
117 canonical draft pairs (85 head-off, 32 head-on), and 32 eligible recursive
captures/restores. Planning verifies prompt-token compact-JSON digest, target
identity, vocabulary, context, F32-target/BF16-draft arithmetic, exact draft
manifest SHA, experts mode, full pair sequence and actual d1/d2 reference rows.
The reference is evidence only; it never supplies a runtime target input.
`scripted_proposal_tokens`, forced misses and speculative proposal use are refused.

```sh
python3 engine/tools/ring_live_driver.py --config /absolute/config.json --plan /absolute/plan.json
```

This command only plans. The run coordinator supplies explicit existing unit and
hash-bound admission for `--run`; the unchanged cooperative lifecycle handles
fault/holder monitoring, final DUMP, postflight and FINISH. No restart loop or
independent device access is added. Native flags are
`--pipeline-ring --pipeline-ring-live-draft --pipeline-ring-request-sha256 HEX`
on every owner; stage zero also receives
`--pipeline-ring-recursive-verify-restore --pipeline-ring-final-shared PATH` and
the authenticated existing draft options. Native ring-live implies the required
provider partition internally.

Evidence includes `provider-batches.jsonl` written before reference comparison,
verified target commands in `schedule.jsonl`, committed `tokens.jsonl`, and
`ring-live-result.json` (`ownrt.ring-live-driver-result.v1`). That result hashes the
unchanged inherited lifecycle result and plan, explicitly labels actual-provider
quiescent execution, and makes no speed claim. It is not the final qualification:
compare all canonical 73 draft allocations/layouts and host metadata against the
accepted live PP4 state, all canonical target state, actual native d1/d2 batches,
independent final-peer binding, private inventory and complete restore counters.
The six independent CPU-reference disagreements remain unresolved by this gate.

CPU tests from `engine/tools`:

```sh
python3 -m unittest test_ring_live_wire test_ring_live_driver -q
```

Tests include actual fragmented socket workers on 2/4/6 owners, local ACCEPT
before provider and before forwarding, read-only-peer-equivalent record checks,
all 360 final-record bytes mutated, wrong request/seed/parent/serial/restoration
metadata, stale/truncated replies, owned hidden lifetime, draft identity mismatch,
actual-guess disagreement with target without changing target history, and
hash-bound truthful result metadata. No GPU or model payload read is needed.
