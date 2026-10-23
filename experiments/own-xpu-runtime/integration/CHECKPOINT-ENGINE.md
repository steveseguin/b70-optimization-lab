# Experimental checkpoint policy adapter

[checkpoint_engine.py](checkpoint_engine.py) connects an already attached
protocol-v2 `NativeFront`, [NativeCheckpointStore](native_checkpoint_store.py),
the explicitly selected p198 [checkpoint bridge](checkpoint_bridge.py), and
[Parking](../../../tools/ctxkeeper/parking.py). It does not launch an owner,
start HTTP serving, signal a process, restart a service, or serialize native state.

The constructor requires the complete expected engine identity, the explicit
`v1.2+p198` contract, the admitted checkpoint root, a positive conservative
new-checkpoint peak-size bound, and a free-space callback plus reserved floor.
It checks the experimental label, native binary and store bindings, protocol,
context, vocabulary and one-load readiness. The owner coordinator must supply
these values from trusted launch provenance. A readiness event does **not** attest
the owner binary or startup checkpoint root. No identity is learned from the
checkpoint being inspected; native labels and raw manifest bytes remain intact.

`save_size_bound_bytes` has no default. The caller must bind its proof to the
admitted native geometry/context and writer. It includes metadata, tokens,
control files and staging, not just state tensors. Parking reserves the peak
with old and retained checkpoints still counted. The adapter additionally
checks actual filesystem headroom before each SAVE. Actual closed-inventory
`storage_bytes` comes from the locked store snapshot and is returned in policy
metadata; metadata inspection does not claim full tensor validation.

The public operations have these meanings:

| Operation | Behavior |
| --- | --- |
| `identity()` | Returns the injected model and native binary digests. |
| `inspect(id)` | Takes a locked snapshot, validates exact trusted p198 identity and small payloads, returns a policy projection or proven missing. |
| `delete(id)` | Uses the native store's typed `ok`, `in_use` or `missing` result. No recursive filesystem deletion. |
| `save_size_bound(id, tokens)` | Returns the injected conservative new-state peak bound without SAVE. |
| `save(id, tokens)` | Requires the adapter's current complete reply, exact full visible token vector, a fresh ID and headroom; sends one SAVE and validates its acknowledgement against a locked native snapshot before returning metadata. |
| `restore(id, tokens)` | Records a validated append-only plan. It does not decode. Input must include the saved pending token; same-generation resume is not supported by this API. |
| `generate(tokens, max_new, request_id=...)` | Revalidates and consumes any pending restore plan exactly once, then sends one RUN. The native engine still performs all checkpoint checks before upload. |
| `release()` | Sends one RELEASE for the adapter's pending reply. |
| `run_turn(parking, session, messages, request_id=..., max_new=...)` | Holds one mutex across policy lookup, generation and postreply parking/disposition. |

The normal policy sequence is `before_request → restore plan if selected →
generate → park`. If park returns normally and no SAVE disposed the reply, the
adapter sends RELEASE. This includes a `None` no-save decision **and** a non-None
same-ID hit. Final-request RELEASE leaves the front draining; a coordinator
retains ownership of the final stopped-event and process-drain checks.

Every exceptional operation halts subsequent adapter intake. An ambiguous SAVE,
changed checkpoint, wrong identity, storage failure or policy exception causes
no automatic retry, RELEASE, close or signal. The existing coordinator owns
incident handling. Parking keeps ambiguous reservations charged. Typed missing
inspection and `in_use` deletion are normal outcomes. All use of the attached
front must remain exclusive to this adapter; external direct RUN/SAVE calls
would bypass its mutex and are outside the contract.

[test_checkpoint_engine.py](test_checkpoint_engine.py) uses explicitly synthetic
metadata envelopes and mocked front/store objects. It exercises trusted identity,
full visible histories, append-plan consumption, same-ID/no-save releases,
final-request disposition, headroom, ambiguous failures, retained reservations,
and mutex ordering. These CPU fixtures do not qualify native arithmetic, actual
store locking, HTTP serving, or a live model integration. The owner must separately
authorize isolated real-host fixtures and any eventual live wiring.

## Host integration proof, 2026-10-23

The [corrected host probe](receipts/checkpoint-engine-host-b-closeout.json) passed
one unchanged packet198 GNU HOST_ONLY owner: eight requests, 44 generated tokens,
five saves, three releases and clean stopped. It exercised the actual front,
native locked store, bridge, bounded parking policy and adapter together on
context64/vocab16 synthetic geometry. Restored append matched fresh tokens and
state exactly; edited-prefix prefill, normal no-save and same-ID release passed.
The [six-section closeout](../notes/2026-10-23-checkpoint-engine-host-closeout.md)
preserves failed attempt A, corrected attempt B, source identities and scope.

This proof is distinct from the [packet198 device lifecycle audit](../stage2/packet198-postreply-checkpoint/evidence/independent-device-result.json),
which validated 1,408 real-model tokens and five state snapshots through its fixed
worker. The policy/adapter integration has only the tiny host proof. ctxkeeper's
HTTP request path remains unwired; no live model endpoint, serving qualification,
throughput claim or release bump follows from this result.

## Joined real-model proof, 2026-10-23

[Packet199](../stage2/packet199-chat-parking/RESULT.md) subsequently passed six
actual HTTP turns through one unchanged device owner, this adapter stack and
bounded parking: 896 output tokens, five saves and one release. Resumed chat
matched fresh tokens and saved state; edited history selected fresh processing.
The independent audit verified HTTP mapping and usage and rehashed both surviving
checkpoints. Policy-deleted states retain captured digest evidence, with that
limitation explicit. All replies reached their caps. This is a bounded functional
pilot, without a general serving, natural-stop, cold-speed or throughput claim.
