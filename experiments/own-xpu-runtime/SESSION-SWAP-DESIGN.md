# Session Swap Design — Checkpoint/Restore for the Own Runtime

**Status: PROPOSED — EXPERIMENTAL.** Checkpoint restoration is labeled
experimental everywhere (interface, manifests, pages) until the
restart-and-continue exactness test in §7 passes on a supported host.
This document is the contract the ctxkeeper integration builds against.

## 1. Scope

v1 is deliberately the smallest honest thing:

- **Configuration:** the packet165 one-card (TP1) full512 profile — Qwen3.8
  Flash-Next UD-IQ3_XXS, one B70, context allocation 4096, BF16 KV,
  greedy argmax only (no sampler state exists: no RNG, temperature, top-k/p
  anywhere in the engine), target-only (no MTP; `main.cpp:269` requires
  `!a.mtp`).
- **Operation:** save one complete computed session, stop the runtime,
  restart it, restore, and continue decoding correctly.
- **Measured alongside correctness from the first milestone:** save bytes,
  save time, restore time (disk read + upload + re-admission), versus cold
  prefill of the same prefix. Geometry-derived sizes below are calculations
  until measured; nothing here is an estimate presented as a result.
- **Not in v1:** selective block reuse, cross-session state moves, TP2
  (adds MTP draft state and rank0 state banks), context editing, quantized
  checkpoint encodings.

## 2. What a checkpoint contains (TP1 state inventory)

Per-session mutable device state, from the packet165 engine sources
(`one-card/lineage/native/generated/main.cpp`, plan builder `plan.hpp`,
geometry `api.hpp`; all sizes BF16, context 4096):

| State | Shape × count | Bytes | Position-dependence |
|---|---|---|---|
| QSA `keys`+`values` | {4096,2,256} ×2 ×12 layers | 100,663,296 | slice to `position` |
| QSA `raw` (indexer) | {4096,128} ×12 | 12,582,912 | slice to `position` |
| QSA `pooled` | {1024,128} ×12 | 3,145,728 | slice to `position/4` |
| GDN `history` (conv) | {10240,3} ×36 | 2,211,840 | fixed |
| GDN `state` (recurrent) | {48,128,128} ×36 | 56,623,104 | fixed (encodes whole prefix) |
| PLE `history` + `token_history` + `ple_metadata` | blk.1 | 184,616 | fixed |
| Controls (`token`,`position`,`active`,`error`,`next_token`) + `streams` | | 20,500 | scalar |
| Token array (host) | ≤4096 × i32 | ≤16,384 | the prefix itself |
| **Total, full 4096 fill** | | **≈175.4 MB** | |
| **Total, typical 2048 fill** | | **≈114 MB** | |

Full allocation dump already exists: `pipeline::state_dump`
(`rank.hpp:188-196`) writes every plan buffer plus a sha256 manifest
(`state.json`). The checkpoint format refines this: KV-family buffers are
sliced to the admitted position (dim0 is the position axis), GDN/PLE/controls
are fixed-size. Host mirrors that must be recorded for exact resumption:
`history0/history1` (int64 pair), launch-extent mirrors
(`context_extent`/`alternate_context_extent`, re-derived at restore by
`admit_position(max_position)`), and the full token array with its sha256.

Immutable and therefore excluded: model weights (≈82 GB, three GGUF shards
pinned by `identity.tsv`), `rope.bf16` (sha256-verified at startup), expert
cache contents (immutable weights; residency is performance state only —
restore re-warms through normal misses, documented as a first-decode-after-
restore timing effect, never a correctness input).

## 3. Interface contract

Four operations on checkpoint directories, caller-supplied `checkpoint_id`:

```
save(session, checkpoint_id, dir)      -> manifest.json
inspect(checkpoint_id | dir)           -> manifest.json   (no device required)
restore(checkpoint_id, dir, prompt)    -> session         (fail-closed)
delete(checkpoint_id, dir)             -> ok | in_use
```

- **save** blocks only at a decode boundary (between tokens, never
  mid-step). Writes `manifest.json` + one blob per state array, slices KV to
  position, sha256 per blob, fsync, then marks the checkpoint `visible`.
  A partial or unverified checkpoint is never visible to restore.
- **inspect** reads the manifest without touching a GPU: model identity,
  engine binary sha256, geometry, dtypes, token count, position, created
  time, per-blob sizes/hashes, and the `experimental` label. This is how the
  integrator enumerates parked sessions and pre-checks restorability.
- **restore** runs every compatibility check (§4), uploads blobs into the
  freshly allocated plan buffers at the per-request hook (in place of
  `p58_reset_request`, `main.cpp:1975`), sets `position`/`token_history`/
  `history0/history1`, calls `admit_position` so prepared launch extents
  match, then returns a session positioned exactly where save blocked.
  `prompt` must extend the recorded prefix exactly (§5) or restore refuses.
- **delete** removes the directory; an in-flight restore holds a lockfile
  and delete reports `in_use`.

All primitives needed already exist (`Engine::upload`/`readback`/`put`/
`admit_position`, `main.cpp:887-926,1572-1578`). No new device machinery.

## 4. Compatibility checks (restore refuses unless ALL pass)

1. **Model identity** — checkpoint manifest's weight hashes == the running
   model's sealed hashes.
2. **Engine identity** — checkpoint's `binary_sha256` == running binary's
   (v1 exact-match; a qualified-upgrade mechanism can later admit binaries
   whose qualification record covers the same arithmetic profile).
3. **Geometry** — 48-layer layout (12 QSA @ blk 3,7,…,47; 36 GDN), head
   counts/dims, context allocation ≥ recorded position.
4. **Dtypes** — BF16 KV, BF16 GDN state (certified inter-row layout),
   PLE dtypes.
5. **Token state** — recorded token array length == recorded position;
   length ≤ context allocation.
6. **Host/device** — B70 device family; oneAPI/Level-Zero versions inside
   the qualification record's tested set.

Any failure names the failed check; there are no silent fallbacks and no
approximate restores.

## 5. Prefix-plus-delta rules

- Cached QSA KV and GDN recurrent state both encode the **entire preceding
  sequence**. They are not movable to other prefixes; correcting positions
  does not make blocks interchangeable.
- A checkpoint is valid only for its exact recorded token prefix.
  **Continue = append a delta** to that prefix.
- Any edit, insertion, or deletion inside the prefix invalidates the whole
  checkpoint. v1 does not attempt downstream-state salvage; selective
  invalidation is a follow-up that must prove which state survives.
- Integration consequence: note edits land in the appended delta (the new
  view), or the session re-prefills. `restore()` takes the continue-prompt's
  prefix hash and refuses unless it extends the recorded prefix exactly.

## 6. Checkpoint manifest (sketch)

```json
{
  "format": "ownrt.session-checkpoint.v1",
  "label": "experimental",
  "checkpoint_id": "caller-supplied",
  "created": "ISO-8601",
  "model": {"weights_sha256": "…", "identity_tsv_sha256": "…"},
  "engine": {"binary_sha256": "…", "packet": "packet165", "profile": "tp1-full512"},
  "geometry": {"layers": 48, "qsa_layers": [3,7,…,47], "kvh": 2, "ad": 256,
               "gdn": {"kh": 16, "vh": 48, "d": 128}, "context": 4096},
  "dtypes": {"kv": "bf16", "gdn_state": "bf16", "ple": "bf16"},
  "token_state": {"length": N, "position": N, "tokens_sha256": "…",
                  "token_history": […, …]},
  "sampler": {"mode": "greedy-argmax", "state": null},
  "blobs": [{"name": "blk.3.qsa.keys", "bytes": …, "sha256": "…", "slice": [0, N]}],
  "measurements": {"save_seconds": …, "save_bytes": …}
}
```

## 7. Exactness and measurement gates (the exit criteria for "experimental")

Reusing the packet165 harness disciplines (`measurement.py` stream checks,
fresh-process repeat equality):

1. **Restart-and-continue (correctness):** run a request to token K, save,
   kill the process, restart, restore, decode to K+M. The M restored tokens
   must equal, bit-for-bit, an uninterrupted fresh-process reference run of
   the same prefix. Oracle-prefix discipline as in the sealed profiles
   (oracle cap 128 for the gate; full-array comparison for the receipt).
2. **Repeat determinism:** two independent save→restore→continue cycles from
   the same checkpoint produce identical continuations.
3. **Cold-start comparison (speed, reported alongside):** restore time
   (disk read + upload + admission) vs cold prefill of the same prefix, same
   host state. Published with bytes actually read, not derived.
4. **Admission discipline:** device runs follow the sealed-window rules
   (whole-host reservation, fault review, disk/memory floors) exactly as the
   packet165 requalification did.

## 8. Relationship to existing mechanisms

No exclusivity is claimed. vLLM exposes external KV-cache connectors
(`kv_transfer` KVConnector API) and llama.cpp exposes session-state
save/load (`llama_state_*`). Their compatibility with this B70/IQ3_XXS
stack is unverified here. The contribution of this work is a validated,
measured checkpoint/restore for our hardware under our bit-exactness
requirements, integrated with ctxkeeper's parking policy.

## 9. ctxkeeper integration boundary

- **ctxkeeper owns:** durable conversation records, parking policy (which
  sessions to park, when, eviction), textual recall for the cold tail.
- **Runtime owns:** the four operations, compatibility checks, exactness
  gates, and measurement receipts. ctxkeeper never writes checkpoint
  internals; it addresses checkpoints by id and consumes `inspect` output.
- GDN recurrent state is position-free fixed-size (56.6 MB) — it summarizes
  the whole prefix in constant space; attention KV scales with fill
  (≈28.4 KB/token across the 12 QSA layers at this geometry). Parking cost
  is therefore dominated by the fixed GDN floor at short contexts and by KV
  at long ones. [calculated; §7.3 measures]

## 10. Follow-ups (post-v1, in order)

1. TP2 checkpoints: MTP draft state (`mtp36::DraftRuntime` buffers) and
   rank0 `state_spares` banks; two-card atomicity (both ranks or none).
2. Selective prefix-truncation reuse (drop a suffix, keep earlier state) —
   provable for KV slices, needs a GDN-state answer (GDN cannot un-see
   tokens; truncation past the last GDN checkpoint requires saved GDN
   snapshots, e.g., per-boundary GDN snapshot ring).
3. Checkpoint compression/encoding (the QSA `raw`/`pooled` indexer forms
   are already compressed views; evaluate drop-and-recompute vs store).
4. Multi-session parking pool with admission control under VRAM pressure.
