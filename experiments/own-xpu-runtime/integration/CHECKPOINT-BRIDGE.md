# Native checkpoint metadata bridge

CPU implementation, 2026-10-23. `checkpoint_bridge.py` connects packet181's
native checkpoint metadata to the token-prefix convention used by ctxkeeper's
parking policy. It performs no I/O, native execution, device initialization or
checkpoint mutation. The warm request front is still missing. This is not a
serving or device qualification, and does not change any sealed engine identity.

## The two token histories

For a native checkpoint, `tokens.bin` contains the **processed** prefix H as
little-endian signed 32-bit token IDs. `token_state.length` and `position` are
`len(H)`. `tokens_sha256` hashes those exact binary bytes. `next_token` is a
separate pending token t that the caller has seen but the model has not processed.
`token_history` is the last two processed IDs, not the complete prefix.

The parking policy instead compares the complete caller-visible history
`H + [t]`, hashing a compact JSON integer array. Passing through the native
manifest would compare different hash encodings and omit the pending token.

`validate_snapshot(...)` requires successful native inspect output, the exact
manifest bytes, `tokens.bin` bytes, `next_token.bin` bytes, checkpoint ID and
the admitted running engine's identity. It verifies the inspect envelope and
manifest hash, embedded manifest agreement, contract/label, identity fields,
processed length/position/history, token vocabulary, binary token hash and
pending control value/hash. Metadata inspect must not claim full verification;
full inspect must report the exact verified blob count and bytes.

Two outputs have distinct purposes:

- `view.parking_metadata()` returns `ownrt.parking-checkpoint-view.v1`, a
  **policy-only projection** with length `len(H)+1` and the JSON-prefix hash.
  It preserves the source's model, engine, label, contract and blob sizes,
  and retains the original token state under `bridge.native_token_state`.
  Never write this projection into a native checkpoint directory or supply it
  to the native manifest reader.
- `view.plan_append(input_tokens, max_new=...)` requires exactly
  `H + [t] + delta`, validates vocabulary/context bounds, and returns the
  complete native input plus the manifest digest to bind at execution. IDs must
  satisfy the native 64-character bound and cannot end in `.lock`; `max_new`
  must stay within the native 1–512 range as well as available context.
  Native append processes **t plus delta**, so its prefill count is
  `1 + len(delta)`. A missing or changed pending token is refused. This API
  never infers same-generation resume from an original prompt.

## Request-front contract still to implement

The trusted local backend must supply identity from its admitted running engine,
not from the checkpoint being tested. `IDENTITY_FIELDS` compares model stat-pin
metadata, engine, geometry, dtypes, tokenizer identity, contract, label and
qualification metadata exactly. This first bridge accepts the existing
`v1.2+p181`, `qualified-one-card`, `tp1-full512` contract only. Historical fixture
identity is test input; it must never stand in for a successor's live identity.
The proposed packet197 `experimental-warm-front` / `v1.2+p197` contract is
deliberately refused by this version. Wiring it requires an explicit, separately
tested bridge extension and the actual admitted successor identity; it cannot
inherit packet181's qualification label or gates.

Capture native inspect output and these small payloads under the native shared
checkpoint lock. The pure bridge does not implement directory access or locking.
At execution, reacquire/retain the native lock, require the planned manifest
digest still matches, then run **all native full restore checks**, including
every state blob, current engine/model/tokenizer/geometry, state completeness
and semantic controls, before any upload. A successful metadata plan does not
replace those checks. Preserve per-request reset before applying sliced state.

The future backend can use the projection for `parking.Engine.save/inspect`
results and the explicit plan for its `restore` operation. It must only save
the actual running session at a drained boundary and must verify that the
policy's supplied history equals that session's processed prefix plus pending
token. It must preserve inspect/delete locking and `in_use` errors. The
current module implements neither save/restore/delete nor an `Engine` backend.

A changed prefix, note edit, trimmed tail or incompatible checkpoint is a
named miss/refusal; the policy may choose a fresh prefill. A runtime/device
fault must halt new requests, with no retry or process restart. No checkpoint
reuse belongs in a cold record claim.

## Evidence

`checkpoint-fixtures-p181/` contains exact copies of packet181's device
lifecycle S1 metadata-inspect and S2 full-inspect outputs and manifests.
Small binary payloads are losslessly hex-encoded JSON fixtures; there are no
compiled payloads. `provenance.json` records original paths, hashes, encodings
and every copied fixture hash. The historical identity fixture is an explicit
projection of the actual S1 manifest, not a fabricated qualified engine.

S1 replays the real 469-token append: **342 processed + pending token 37574 +
126 delta**, giving 343 saved-history tokens and 127 native prefill tokens.
S2 replays 596 processed tokens plus pending token 11. The tests exercise the
unchanged `tools/ctxkeeper/parking.py` policy read-only: the normalized real
checkpoint is a hit, and a pending-token edit becomes a miss. Negative cases
cover corrupted/wrong-endian/truncated payloads, manifest edits, every identity
field, inspect failure/overclaims, pending controls, context bounds and malformed
JSON. No native process is invoked.

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/integration -p test_checkpoint_bridge.py -v
```

All 17 tests passed. The source and fixture hashes are retained in
`receipts/checkpoint-bridge-cpu-20261023.json`. No serving or performance claim
is attached to this bridge.
