# Packet 181 — session checkpoint v3: `qualified-one-card` label, packet180 read compatibility, prompt-path record

**Status: CPU-prepared, sealed, READY, proposal written (not queued); device qualification of this
binary pending.** Child of [packet180](../packet180-session-swap-v2/README.md) (append +
restore-then-save, device-qualified 2026-10-22). Entry TU only; all 41 kernel objects relinked
byte-identical from packet165 exactly as packet179/packet180 did; arithmetic untouched.

Device binary `one-card/build/device/own-rt-iq3`:
**`0bf0a17ac215a7dc552de9337a2d549172552a8641e0ec7334e83af5c67829fd`** (built three times from the
same source: identical). Arithmetic parent packet165 `1364bb3d…`; previous checkpoint engine
packet180 `f68714ce…`.

## Append prefill: what the engine does (the brief's item 1 was not built, and why)

The brief asked for appended tokens to go "through the same chunked prefill mechanism" a fresh
request uses, instead of "the incremental (decode) path". **The engine has no chunked or batched
prefill.** A fresh request steps its prompt one position at a time through the prompt step
(`step(token, 0)`: every layer launch except final norm/logits/argmax, then `step(last, 1)` for the
first generated token). packet180's append calls that same lambda for positions `[N, len(input))`
— it was never the decode path. `prefill512` is the name of a 512-token suite prompt, not a chunk
size. Batched prompt reading was studied in
[packet165/BATCHED-PREFILL.md](../packet165-warm-prefill/BATCHED-PREFILL.md) and its first device
step, the fully paired causal M=2 layer of [packet166](../packet166-m2-layer-micro/DO-NOT-REPEAT.md),
was **closed** (measured layer M2/M1 > 1.5; routed expert gate/up 2.81×, down 2.08×). Building it
would need new M>1 kernels (not an entry-TU change) and would reopen a closed lever, so this
packet does not.

Why packet180's append looked slower (127 tokens in 5.59 s ≈ 22.7 tok/s vs 469 in 16.0 s ≈ 29
tok/s): every leg of row b is a **fresh process with an empty expert cache**. Per-position
prompt-step cost from packet180's real `prefill-timings.jsonl`
(`one-card/evidence/p180-receipt-replay.json`, `prompt_mechanism_evidence`):

| Process / positions | mean ms per prompt step |
| --- | --- |
| cold reference, positions 0–63 / 64–127 / 128+ | 52.1 / 37.8 / 28.6–31.7 |
| append, positions 342–405 / 406–467 (first steps of its process) | 53.9 / 33.8 |
| row a `prefill512` (second request, warm process), 0–63 / 64+ | 32.9 / 27.1–33.1 |

At matched warmth the append is **not** slower: its 126 prompt steps took 5549 ms against 5684 ms
for the cold reference's first 126 (ratio 0.976). The reference ran the same positions 342–467 in
3839 ms because its cache was warm by then. The gap is the cache fill a fresh process pays on its
first positions, spread over 127 appended positions instead of 469. In a long-running server the
cache is already warm and an append runs at the warm rate.

**Byte identity.** The append is byte-identical to the one-shot run by construction (same prompt
step, same positions, restored state byte-equal to the one-shot state at N) and was proven on
device by packet180 (append == reference [0:128], S2 == S2b blobs). A future batched prefill would
be byte-identical only if each M>1 operator kept every row's M=1 reduction order, split tree and
BF16 rounding points and the GDN recurrence stayed sequential with BF16 state stores between rows
(BATCHED-PREFILL.md exactness contract; packet166's paired layer kept every byte equal to two
M=1 calls in its device run, `finite_bytes_equal: true` in `evidence/layer-micro-B1/analysis.json`). Chunk boundaries after a restore would then not change any byte,
because the restored state equals the one-shot state at N. Nothing in this packet depends on that.

What packet181 adds for item 1: every `result.json` records which positions were stepped and how
(`checkpoint.prefill`, `restore.append_prefill_tokens`, `restore.append_prefill_path`); row b
gates that the append path equals the fresh reference's path (both `incremental`, the engine's
only mechanism) and reports the append cost per token against the cold rate (the brief's ×1.25
bound) and at matched warmth. The ×1.25 bound is **expected to be exceeded** (~1.29, as packet180
measured) for the reason above; it is reported, never a gate.

## What changed (entry TU only)

| Item | Change |
| --- | --- |
| Label | manifests are written with `label: "qualified-one-card"`, `contract: "v1.2+p181"` and a `qualified_by` object (below); `engine.packet` is `packet181-session-swap-v3` |
| Compatibility | the reader accepts both `v1.2+p181` (label `qualified-one-card` + exactly this engine's `qualified_by`) and packet180's `v1.2+p180` (label `experimental`, no `qualified_by`). Label and contract must pair; anything else is a malformed manifest. Whether a checkpoint can be **restored** is decided by the identity and semantic checks (binary, geometry, model, tokenizer, token state, blobs), never by the label |
| Prompt record | `result.json` `checkpoint.prefill` for every request; `append_prefill_tokens`, `append_prefill_path` in `checkpoint.restore` |

Native delta: [`lineage/packet181-vs-packet180-main.patch`](one-card/lineage/packet181-vs-packet180-main.patch)
(main.cpp +8/−1: the prefill record arguments),
[`packet181-vs-packet180-checkpoint.patch`](one-card/lineage/packet181-vs-packet180-checkpoint.patch)
(checkpoint.hpp +85/−15; 919 → 989 lines), `packet181-native-delta.patch` (main.cpp vs packet165:
+94/−6). The authoritative header is [`checkpoint.hpp`](checkpoint.hpp) at the packet root;
`adapt_native.py` installs it. **The CLI is unchanged** (`native-help-flags.json` byte-equal to
packet180's); operation semantics (save, same-generation resume, append, restore-then-save,
inspect, delete, locking, refusals) are exactly
[packet180's](../packet180-session-swap-v2/README.md#operation-semantics).

### `qualified_by` (written verbatim; required structurally equal on read)

```
{"scope":"one card (tp1-full512 profile) only; TP2 checkpoints not implemented; no ctxkeeper adapter yet",
 "device_gates":[{"packet":"packet179-session-swap","date":"2026-10-22","operations":["same-generation-resume"]},
                 {"packet":"packet180-session-swap-v2","date":"2026-10-22","operations":["append","restore-then-save"]}]}
```

Manifest key order: `format, label, contract, qualified_by, operations, …` (the rest as packet180).
`fields.tsv` for `v1.2+p181` adds two rows after `contract`: `qualified_scope` (the scope string)
and `qualified_by` (`packet179-session-swap@2026-10-22:same-generation-resume;packet180-session-swap-v2@2026-10-22:append,restore-then-save`).
A `v1.2+p180` manifest renders exactly as packet180 rendered it (packet180's device S1/S2
`fields.tsv` pass this reader verbatim).

### result.json additions (additive)

```
"checkpoint":{"contract":"v1.2+p181","label":"qualified-one-card","operations":[…],
  "prefill":{"path":"incremental"|null,"first_position":p,"tokens":n,"ms":prefill_ms},
  "restore":{… packet180 fields …,"append_prefill_ms":ms|null,
             "append_prefill_tokens":len(input)-N (0 for resume),"append_prefill_path":"incremental"|null},
  "save":…}
```

`prefill`: fresh run `[0, len(input))`; append `[N, len(input))` (the pending token first, then
the delta; `ms` = `append_prefill_ms`); same-generation resume `tokens: 0, path: null`. `ms`
equals the top-level `prefill_ms`. Analyzers read a missing field (packet180 receipts) as
`incremental` — correct, because packet180 stepped appended tokens through the same prompt step.

## CPU gates (all passed; receipts in `one-card/evidence/` and `evidence/`)

| Gate | Receipt | Result |
| --- | --- | --- |
| Native delta + harness edits | `native-delta.json`, `delta-check.json` | entry TU only; every other copied file byte-equal to packet180 after path relocation; packet180's `measurement.py` is an exact prefix of this packet's (its analyzers unchanged) |
| Device build | `build.json`, `identity-check.json` | icpx compile + link ~30 s; 41 kernel objects sha-asserted vs packet165; binary differs from packet165 and packet180 |
| Host-only C++ sessions | `checkpoint-probe.json` | 91 native runs. packet180's cases: round trip; append == fresh reference; restore-then-save chain ×2 == reference; repeat append and a fresh one-shot save hold byte-identical state blobs; empty-delta append == resume; inspect modes; **26 refusal/boundary cases**; 14 delete cases incl. a real concurrent delete-vs-restore. New: manifests carry the v1.2+p181 identity and the C++ `fields.tsv` equals a Python port of the renderer; prompt record on every leg; **append-span variants** (1-token delta; 28-token delta crossing position 32; restore at N=13, not a multiple of 4, then a 25-token delta crossing 32) each == the one-shot reference with state byte-identical to a fresh save; **label compatibility**: an `experimental` v1.2+p180 checkpoint is inspected, resumed, appended and restore-then-saved (child is v1.2+p181 with identical state, resumes == reference), deleted; it is refused only by an identity check (binary mismatch → `engine identity`); 8 pairing refusals (label/contract mismatch both ways, `qualified_by` edited/missing/added to v1.2+p180, contract `v1.2+p179`, unknown label) before model load |
| Production shape | `checkpoint-probe.json` `production_shape` | packet179's real 128-blob checkpoint converted to v1.2+p180 *and* to v1.2+p181: metadata + full inspect (real control-blob checks), TSV tamper refused, delete; **packet180's real device S1 and S2 (v1.2+p180, `experimental`) pass metadata + full inspect verbatim** and the delete tool on scratch copies; S1 passes the whole pre-load restore precheck with the real 469-token NEW (the mini probe then stops at its own token-range check; on device the engine-identity check refuses a packet180 checkpoint) |
| Lifecycle worker arm (production shape) | `lifecycle-test.json` | real `worker.lifecycle()` with mocked native: 87-token P, K=256, 126-token T, NEW=469, packet180's real S1 manifest layout relabelled; 20 cases: all packet180 failure cases (first index + both streams), plus append path `chunked`, reference path differing, wrong `append_prefill_tokens`, resume recording a path, manifest label `experimental` under v1.2+p181, `qualified_by` missing/different — each fails exactly its gates; an append outside the ×1.25 bound still passes (reported only) |
| packet180 real receipts | `p180-receipt-replay.json` | packet180's `lifecycle_check` reproduces packet180's device receipt exactly (36 gates, comparisons, timing); the v3 analyzer passes the same receipts (38 gates, missing path → `incremental`), reports ×1.29 overall / ×0.976 matched warmth; with `expect=v1.2+p181` it fails exactly the 3 label gates and 5 record gates; row a: aggregate and report reproduce **31.78 tok/s**, packet180's 13 outputs == packet179 row a |
| Inherited | `p179-receipt-replay.json`, `analyzer-tests.json`, `report512-test.json`, `real-arm-sequence.json`, `native-sequence.json`, `device-path-imports.json`, `preparation-probe.json`, `flags.json`, `../evidence/packet163-replay.json` | unchanged gates re-run on this packet |

## Device rows (proposal only: `ops/lane-queue/proposed-p181-one-card-A.txt`)

Admission exactly as packet180's rows: lane A whole-host reservation, fault review
(`one-card/fault_review.py`), host memory admission 98,990,252,032 bytes available, device storage
floor 25 GB (`screen.py`, at start and throughout), lane-queue storage floor 25 GB +
`planned_write_bytes` (400 MB) at plan/launch, worker supervision 7200 s (`screen.py`), native
`--seconds 7200` and `--wait-seconds 600` per process.

| Row | What | Estimate |
| --- | --- | --- |
| `packet181-one-card-full512-A-a` | full512 suite (one load, 13 requests, oracle-128); every request's full output must equal packet179 row a (`run/p179-identity.json`), which packet180 row a equalled on all 13 | ~8.5 min (packet180: 500 s); plan range 450–900 s |
| `packet181-one-card-lifecycle-A-b` | packet180's five fresh processes unchanged: save S1 (K=256) → restore + append T (126) + 128 + save S2 → resume S2 + 64 → fresh reference of NEW (192) → repeat append into S2b; then inspect-metadata S1/S2/S2b, full inspect S2/S2b, delete S2b | ~20 min (packet180: 1167 s = five loads of 209–215 s + 4.5–38 s requests + tools); plan range 1100–2400 s |

Row b gates (43): packet180's 36 with its three manifest identity gates re-evaluated for
v1.2+p181 (label `qualified-one-card`, `qualified_by`, `engine.packet`), plus: append prompt path
== reference prompt path == `incremental` (append-s2, append-s2b), and the prefill/append records
of all five legs. **A divergence is a FAILURE** with the first divergent index and both streams in
`run/lifecycle-receipt.json`. Reported, not gated: restore ms, append prefill ms per token vs the
cold rate (×1.25 bound, expected ~1.29) and at matched warmth (expected ~0.98), save seconds/bytes,
cold prefill vs restore + append. The restore of an `experimental` checkpoint is host-only
(packet179/packet180 checkpoints are bound to their own binaries; on device the engine-identity
check refuses them regardless of label).

Numbers above and where they apply: 27 GB = CPU build/probe stop (`build_engine.limits`, this
host's CPU scripts only); 25 GB = device floor (screen, during the row) and lane-queue floor;
7200 s = screen watchdog on the worker child; 600 s = native per-operation wait and the worker's
bound on each device-free host tool; 60 s = CPU-probe-only wait for the concurrency hook; ×1.25 =
reported append/cold ratio bound (analyzer only, never a gate); estimates and `expected_seconds`
are informational (no runner enforces them).

## Packaging order and checks

`scaffold.py` (once) → `adapt_native.py` → `build_checkpoint.py one-card` → `checkpoint_probe.py`
→ `test_measurement.py`, `test_report512.py`, `test_sequence.py`, `test_lifecycle.py`,
`test_p179_receipts.py`, `test_p180_receipts.py` (each `one-card`), `test_packet163_evidence.py`,
`probe_imports.py`, `capture_flags.py one-card`, `native_sequence_probe.py one-card`,
`verify_delta.py` → `package_rows.py` (seal + proposal) → `validate_flags.py` →
`check_queue_rows.py` (live planner and rehearsal on a private copy) → `final_checks.py` →
`final_checks.py --ready` (writes READY last, re-runs `pin_guard.check_job` on both rows over the
full closure). All CPU commands: `nice -n 19 taskset -c 8-15,24-31 … </dev/null` from the repo root.
Result at sealing: seal 688 files; live planner `passed` for both rows before and after READY (root
free 36.9 GB); pin guard on the full closure after READY: 755 pins = 747 in-packet + 7 packet49
oracle-binding targets + 1 own proposal, **0 cross-packet mutable** (both rows; re-checked
independently). Rehearsal warnings are packet180's two (no preparation-path probe declared;
unclassified gate-identity uses). Every pin is packet-private: packet180 receipts are byte copies
under `one-card/lineage/packet180-receipts/` (COPY-MANIFEST.json), packet179's under
`lineage/packet179-receipts/`. The probe reads the real packet179/packet180 device checkpoints in
place (local, untracked blobs) into scratch copies the delete tool removes; nothing outside is
pinned. Commit note: 21 sealed files — the `*.bin` copies under
`lineage/packet180-receipts/row-b/run/checkpoints/{s1,s2}/` (7 each) and
`lineage/packet179-receipts/row-b/run/checkpoints/gate/` (7) — match the repository's `*.bin`
ignore rule and need `git add -f`, or a fresh checkout fails the seal.

## Not claimed

- No device result for this binary: nothing here qualifies its arithmetic or its checkpoints on
  the real model; the CPU equivalence is mini-geometry only. The label states that the operations
  passed device gates in packet179/packet180 on one card.
- One card (tp1-full512 profile) only; **TP2 checkpoints are not implemented**; **no ctxkeeper
  adapter yet** (ctxkeeper does not call these operations).
- **No chunked/batched prefill**: appended tokens and fresh prompts are stepped one position at a
  time; the append prefill timing is an observation of fresh processes, not a performance claim.
- Model identity is host-local (stat pins), not portable; no selective prefix truncation; no
  compression. The tokenizer identity is attested by the caller's file; the engine never tokenizes.
- Restore of a checkpoint written by another binary (any packet179/packet180 checkpoint) remains
  refused by the engine-identity check; label compatibility covers inspect, delete and same-binary
  restore only.
