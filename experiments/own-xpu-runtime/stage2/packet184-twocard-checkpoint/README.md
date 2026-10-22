# Packet 184 — two-card (TP2) session checkpoints on the bundle-8 record line

**Status: CPU-prepared, sealed, READY, proposal written (not queued). Nothing here ran on a device.**
Label `experimental-two-card`, contract `v1.2+p184`: the checkpoint is **not qualified** until the
lane-B rows below pass on device. This is item 1 of §10 in
[SESSION-SWAP-DESIGN.md](../../SESSION-SWAP-DESIGN.md): MTP draft state, the rank-0 `state_spares`
banks, two-card atomicity (both ranks or none).

Device binary `v5/build/device/own-rt-iq3`:
**`ebbc9b151f8f9a0f1cba162abab76872471293fbe9f7e686fb30f800b212c7c5`** (two builds from the final
source: identical). Host build (CPU gates only) `8446c829…d503`; device-free checkpoint tool
`v5/build/tool/own-rt-ckpt-tool` `2226a296…1780`. The device binary was never executed, not even for
`--help`.

## Lineage

| Step | What |
| --- | --- |
| packet136 bundle 8 | two-card record line, 58.798109 tok/s (LocalMaxxing `cmve4dtir007wrf01k57sdf23`); `miss: banks-batch`, `head: head-split-compute`, MTP draft on rank 1, 24/24 split |
| packet153 v5 | packet136 + packet150's one-load v5 harness; lane-B bracket on device 2026-10-19 (controls 58.638/58.671/58.663 tok/s, 13/13 exact) |
| packet184 | identity-rewritten copy of packet153 (`copy_packet184.py`, receipt `lineage/packet184-copy.json`, one recorded vendored amendment) **plus** the checkpoint delta |

Why packet153 and not packet183: packet183 is the same harness plus the S1 dense-scales delta, which
lost on device on 2026-10-22 (metadata views 54.99 vs controls 58.6 tok/s, its `bracket-summary.json`).
Packet184 needs bundle 8 unchanged.

**Parent reproduction.** Before any delta, the copied build (`v5/p184_v5_build_engine.py`) rebuilt
packet153's binaries **byte for byte**: device `106fa3ad…5189`, gnu-host `a36f1405…3bb0`
(`v5/build/parent/build-receipt.json` == packet153's recorded artifacts; checked again by
`v5/p184_build_checkpoint.py`). The toolchain and the relocated sources are the device-proven ones.

## What changed

**Kernel objects: none.** The 78 packet136-lineage parent objects (43 device + 35 gnu-host) are
relinked unchanged, each sha256-asserted against `immutable-binaries.json` before linking.
Recompiled: `entry-main` (the delta below) and `p49d_submit` (unchanged source; packet153 recompiled
it too). New TU: the device-free tool. Zero compiler/linker warnings (the build fails on any).

| File | Change (unified diff: `lineage/checkpoint-delta.patch`) |
| --- | --- |
| `v5/native/checkpoint_format.hpp` (new) | format, strict JSON reader, two-card manifest, `fields.tsv` rendering, load/verify (both rank sets), sibling lock, commit/inspect/delete tools, `--input` classification. Self-contained (std + OpenSSL); also builds the tool |
| `v5/native/checkpoint_tp2.hpp` (new) | rank side: classification over the inventory's enumeration, `stage` (save phase 1), `verify_restore`, `apply_restore` |
| `v5/native-src/rank.hpp` | op 15 (phase 1 stage, 3 verify, 4 apply); op 10 reads `native-resume.txt` (start must equal the restored position, 0 without a restore); the p149 probe exchange is built only at production geometry (inert under `probe: off`; same allocation order on device; lets two-rank `--mini` sessions run on CPU) |
| `v5/native-src/mtp.hpp` | `DraftRuntime::checkpoint_view()` and `checkpoint_restore_host()` (draft position, disabled flag) |
| `native-base/…/native_controller.hpp` | `run(b, c, start = 0)`: a restored session first issues the draft step the uninterrupted run issued at the end of iteration `start-1`, then rank 0 steps `prompt[start]`; `start == 0` is the unchanged fresh path |
| `v5/native-src/main.cpp` | `--checkpoint-*` host-tool hook at entry (packet181 CLI parity) |

Harness: `bracket_config.py` registers the `production` lineage (bundle 8) instead of packet153's
`static`; `cpu_seal.py` rewritten for packet184's gates (`lineage/harness-delta.{patch,json}`). New:
`v5/tp2_checkpoint.py` (coordinator + packet181-shaped CLI), `tp2_lifecycle.py` (device worker),
`lifecycle_report.py`, `checkpoint_screen.py` (derived from the v5 `screen.py` by targeted edits),
`checkpoint_job.py` (queue entry), `checkpoint_ready.py`, the gates listed below.

### vs packet181 (the one-card engine)

Same semantics and CLI shape: save / same-generation resume / append / restore-then-save / inspect
(full and metadata-only) / delete; sibling `<id>.lock` (flock, never waits; shared for restore and
inspect, exclusive for save and delete); `manifest.json` is the only source of truth and `fields.tsv`
must equal its rendering byte for byte; the file set is closed; `--tokenizer-identity` is required
(the same file packet180/181 used, `v5/tokenizer-identity.tsv`). Differences:

* two rank blob sets (`rank0/`, `rank1/`); the manifest names both with sha256 and per-rank host state;
* two-phase save (stage on both ranks, then the device-free commit writes the manifest last) and
  two-phase restore (verify on both ranks, apply only after both verified);
* the coordinator is Python (the two-card engine is two rank processes); flags:
  `tp2_checkpoint.py --checkpoint-save ROOT --checkpoint-id ID --tokenizer-identity FILE`,
  `--checkpoint-restore ROOT --checkpoint-id ID --input FILE --max-new M`,
  `--checkpoint-save-id ID2` (restore-then-save); tools: `own-rt-ckpt-tool --checkpoint-inspect DIR`,
  `--checkpoint-inspect-metadata DIR`, `--checkpoint-delete DIR`, `--checkpoint-commit DIR …`
  (the engine binary accepts the same `--checkpoint-*` tool flags);
* resume bound: `N + 1 + max_new <= context` (the two-card controller steps the pending token as a
  prompt position); restores only by the same engine binary (rank-side `/proc/self/exe` check).

## MTP draft state: saved, not rebuilt

Draft KV row `j` (`blk.0.qsa.keys/values/raw/pooled` of the MTP block) is computed from the target's
layer-47 hidden stream at position `j` and the confirmed token `j+1`. No target buffer retains those
hidden streams (QSA keeps K/V projections, GDN keeps the recurrent summary), so the draft cache cannot
be rebuilt from the saved target state without re-running the whole prefix through the target, which
is a cold prefill. **It is saved**, sliced to the draft's own `position` rows (N−1), with its controls,
host position and disabled flag. The rank-1 target `streams` buffer at the boundary (the hidden stream
of the last processed position, the input of the next draft step) is also saved, because the resumed
controller's first command is that draft step. The manifest records this: `draft.policy = "saved"`,
`draft.reason`, `draft.boundary_hidden_blob = "rank1/streams"`.

CPU proof (`v5/evidence/checkpoint-cpu.json`, `draft`): a forged copy of a checkpoint with the draft
KV zeroed (resealed so it verifies) restores the target exactly (every target blob and every merged
token equal the uninterrupted run), but the draft cache rows stay zero after continuing (all four draft
KV blobs differ). With the saved cache, every draft blob and the merged draft-guess stream equal the
uninterrupted run (`lifecycle`).

## State inventory (TP2), bytes per checkpoint

Real extents at production geometry (`v5/evidence/production-shape.json`, N = 342 = the smoke row's
K=256 save of the 87-token prompt); the N = 4095 column (largest position in the 4096 context) uses the
same per-position extents. BF16 everywhere.

| Rank | State | Rule | N = 342 | N = 4095 |
| --- | --- | --- | ---: | ---: |
| 0 | QSA keys+values, 6 layers (3…23) | sliced [0,N) | 4,202,496 | 50,319,360 |
| 0 | QSA raw (indexer) | sliced [0,N) | 525,312 | 6,289,920 |
| 0 | QSA pooled | sliced [0,N/4) | 130,560 | 1,571,328 |
| 0 | GDN state + history, 18 layers, active bank | whole | 29,417,472 | 29,417,472 |
| 0 | GDN state + history, **spare** bank (`state_spares`) | whole | 29,417,472 | 29,417,472 |
| 0 | GDN state + history, **reserve** bank (`state_reserves`, `miss_banks()`) | whole | 29,417,472 | 29,417,472 |
| 0 | PLE history (blk.1), active + spare + reserve | whole | 552,960 | 552,960 |
| 0 | controls (token, position, active, error, next_token) + token_history | whole | 36 | 36 |
| 1 | QSA keys+values / raw / pooled, 6 layers (27…47) | sliced | 4,858,368 | 58,180,608 |
| 1 | GDN state + history, 18 layers (no banks on rank 1) | whole | 29,417,472 | 29,417,472 |
| 1 | boundary hidden stream (`streams`) | whole | 20,480 | 20,480 |
| 1 | controls | whole | 20 | 20 |
| 1 | MTP draft KV (keys+values, raw, pooled), sliced to N−1 rows | sliced | 807,424 | 9,694,464 |
| 1 | MTP draft controls | whole | 20 | 20 |
| | **rank 0 / rank 1 / total** | | **93,663,780 / 35,103,784 / 128,767,564** | **146,986,020 / 97,313,064 / 244,299,084** |

The spare and reserve banks (59,203,584 B together) are dead at a boundary: the reserve is zeroed by
`SpeculativeImage::boundary()` and the spare is fully overwritten by the next half before it is read
(`RedoBankProof`). They are saved because the brief asked for them; dropping them is an open, unproven
optimization. Skipped (every one by a named rule, recorded in the manifest): plan intermediates fully
rewritten every step (941 / 936 on ranks 0 / 1), QSA ids, `ple_metadata`, transaction scratch
(9 per rank), `mixture-one`, the rollback private image and copy table, p105 head-suffix scratch,
p149 probe scratch, draft intermediates (55) and draft scratch (6). Host fields of the inventory
(`lookup_ids`, `selected`, `loaded_layer`, `fp32_cache`, `bank_parity`, extents, `logical_event`,
`history0/1`, `poisoned`) each have a rule (saved, recorded, re-derived or checked).

**Inventory authority.** The checkpoint classifies exactly the union of the engine's own
`request_state_inventory` + `state_dump` enumeration + `DraftRuntime::dump_all_state`, nothing more
and nothing less, on both ranks: at mini geometry (123 / 179 labels, every saved blob byte-equal to the
dump) and at production geometry (1,110 / 1,091 labels). An unknown persistent-looking name or an
unknown standalone label refuses the save.

## Operation semantics

* **save** (end of a request, decode boundary): the coordinator takes `ROOT/ID.lock` exclusively,
  creates `ROOT/ID/{rank0,rank1}/` and `tokens.bin`; both ranks stage (each proves the lock is held,
  checks position, sticky error, pending token, history mirror, draft position, writes its blobs and
  `stage.json`); the device-free commit tool re-hashes both rank sets, writes `manifest.json.tmp` +
  `fields.tsv`, removes the stage receipts and renames `manifest.json` (the visibility point). Any
  failure removes the invisible directory after both ranks have stopped.
* **restore** (resume or append, by `--input` shape as in packet181): full device-free inspect
  (both rank sets hashed) → shared lock → request reset on both ranks → verify on both ranks (manifest,
  engine binary, geometry, layer sets, model and draft-manifest identity, selection, tokenizer,
  operation, live completeness proof; own blobs hashed and held) → apply on both ranks only after both
  verified (uploads, `history0/1`, `admit_position(N)`, draft host state) → the request runs from
  `start = N`. Every refusal precedes the first upload; a rank refusal fails the whole pair.
* **restore-then-save**, **inspect**, **inspect-metadata**, **delete**: packet181's semantics on the
  two-card layout (lineage parent id + manifest sha256; delete validates its target before taking any
  lock, removes the manifest first, then both rank sets, then the lock).

## CPU gates (all passed; receipts in `v5/evidence/`)

| Gate | Receipt | Result |
| --- | --- | --- |
| Build | `build.json`, `native-delta.json` | both modes + tool, **0 warnings**, 78 parent objects pin-verified, entry TU only, parent reproduction byte-identical; ~76 s |
| Real two-rank sessions on CPU | `checkpoint-cpu.json` | 56 rank pairs of the host engine (`--mini`, bundle 8 with experts/head relaxed: `v5/lineage/mini/`), 79 s. Save at K and restore in a **fresh** pair at N = 12, 31, 32, 34: merged tokens and merged draft guesses == uninterrupted run; **every saved blob of both ranks byte-identical** to a save of the uninterrupted run at the same position; a second independent restore repeats exactly. Append (7- and 25-token deltas, crossing 32) == one-shot run, blobs too; restore-then-save chains == one-shot; empty-delta append == resume. Coverage == inventory (above). Draft necessity (above). 21 refusals, each by the expected check with zero uploads (blob byte on rank 0, rank 1 draft, spare bank; missing/swapped/extra rank sets; `fields.tsv` host value; unsealed and resealed manifest edits; draft position; `tokens.bin`; engine binary; contract; label; wrong pending token; context bound; tokenizer; lock not held). Locks: delete during restore → `in_use`, inspect/restore during save → refused, delete of a non-checkpoint creates no lock, never-overwrite, a rank-1 stage failure leaves no directory |
| Production shape | `production-shape.json` | real v5 startup of both ranks at bundle-8 geometry, numerical device addresses, no payload: fresh startup captures **== packet153 parent** on both ranks (the delta changes no allocation or prepared command); save at N = 342 (93.66 / 35.10 MB), commit, full inspect (216 blobs); fresh-process restore (resume and append) on both ranks: prepared commands == a fresh engine at N, then one real half step (rank 1: the draft step first; rank 0 swaps its banks) with the argument audit re-deriving every prepared block |
| Worker + report rehearsal | `worker-rehearsal.json` | the device rows' own leg functions (`tp2_lifecycle.smoke/lifecycle`) with real two-rank host pairs, real state retention, private drain roots: smoke (2 legs, 11 gates) and lifecycle (3 legs incl. a warm-process session switch, 23 gates) pass; 6 report mutations each fail the expected gate; the report reads one **real** parent-line device request row (packet183's 2026-10-22 bracket, `lineage/parent-device-request.json`) |
| Inherited | `safety.json`, `exec-limits.json`, `admission.json` | packet153 v5 gates re-run unchanged (drain/stop/refusal tests and a platform-math/include scan over all native sources incl. the new headers; pre-exec limit guards; memory ledger) |
| Seal | `v5/cpu-seal.json` | packet184 composition seal (`v5/cpu_seal.py`), mirrored into `lineage/production/screen-seal.json` and `placement-validation/wrapper-seal.json` |
| Queue checks | `check-queue-rows.json`, `queue-plan.json`, `plan-B.log`, `rehearse.json`, `pin-guard.json` | private-copy `lanequeue.py plan --lane B`: **both rows passed** (storage 25 GB + planned writes; host 105,411,248,128 B); `ops/rehearse_entry.py --report`: both rows passed (the real report through `v5/report-contract.json`; WARN: no preparation-path probe declared, unclassified gate-identity uses in inherited files, as packet181/183); live pin guard passed both rows |
| Final | `final-checks.json`, `final-pin-guard.json` | every receipt and key result; drain-fix scan (packet drain code FIXED, the entry's import trace loads only it); READY written last; live pin guard on the full closure after READY: **0 cross-packet mutable pins** |

Packaging order: `copy_packet184.py` (once) → `v5/p184_build_checkpoint.py` → `v5/checkpoint_cpu_gate.py`
→ `v5/p184_checkpoint_shape.py` → `v5/lifecycle_rehearsal.py` → `v5/safety_gate.py`, `exec_gate.py`,
`admission_gate.py` → `package_rows.py` (harness delta, mirror, seal, proposal) → `check_queue_rows.py`
→ `final_checks.py` → `final_checks.py --ready`. All: `nice -n 19 taskset -c 8-15,24-31 python3 -B … </dev/null`
from the repo root.

## Device rows (proposal only: `ops/lane-queue/proposed-p184-two-card-B.txt`)

P = incident-retrospective (87 tokens), K = 256 (save at N = 342), M = 128, T = packet180's 126-token
turn (`v5/lineage/append-delta.json`), R = 64. Every leg is a fresh rank pair (one load, its own
device-isolation monitor, its own serialized drain).

| Row | Legs | Gates | Expected | Watchdog | Planned writes |
| --- | --- | --- | --- | --- | --- |
| `packet184-tp2-smoke-B` | leg1: P×(K+M) uninterrupted reference, then P×K + save S1; leg2: restore S1 + resume M | reference oracle-128; save run == reference[0:K]; merged K+M == reference; merged draft guesses == reference; restore record; checkpoint identity; inspect | 240–480 s | 3600 s | 1.0 GB |
| `packet184-tp2-lifecycle-B` (depends on the smoke) | leg1: P×K + save S1, NEW×(M+R), NEW×M + save SREF; leg2: restore S1 + append T + M + save S2; leg3: restore S2 + resume R, then (same pair) restore S1 + append T + M + save S2b; tools | save run oracle-128; append == one-shot; append + resume == one-shot; warm repeat == append; draft guesses == one-shot; **S2 blobs == SREF blobs** and **S2b == S2** (both ranks); lineage; delete | 360–780 s | 3600 s | 1.5 GB |

Where the numbers come from (informational; no runner enforces `expected_seconds`): a two-card load
took 71 s (warm page cache) and 174 s (cold) in packet183's lane-B windows on 2026-10-22 (rank launch →
device-memory admission in `v5/evidence/device-metadata-{v5,smoke}-B-p183/run/`), a 128-token request
3.2–3.4 s and prompt reading ~13 ms/token (its bracket `report-inputs.json`), a teardown ~3.3 s, the
wrapper ~11 s; save/restore are estimated from packet179/180's one-card device timings (1.10 s / 0.46 s
for 68.8 MB) scaled to 93.7 MB on the larger rank, plus the commit re-hash (0.40 s at production
shape on CPU). Planned writes: checkpoints at their measured sizes (128.8 MB at N = 342, ~136 MB at
N = 596) + the vendored reset's transient raw-state admission (`storage.state_write_bytes(4096)` =
668,210,560 B, hashed and deleted per reset) + logs. Where each number applies: 3600 s = screen
watchdog on the device worker; 27 GB = CPU build/gate disk stop (this host's CPU scripts only,
packet181 precedent); 25 GB = device floor (screen and lane queue, plus planned writes); 300 s =
per-fixture bound of the CPU production-shape gate (packet183 recorded 1.5–2.7 s per fixture run);
3600 s / 1800 s = CPU gate / CPU rehearsal deadlines.

## Two-card admission needs

* **Cards:** lane B = cards 2+3 (`0000:43:00.0` + `0000:47:00.0`). The owner's endpoints on those cards
  (vision :18100 on cards 1+2, `fp8-tp1-test` :18131 on card 3) and `fp8` (card 0, whole-host memory)
  must be stopped, only after `lanequeue.py plan --lane B` passes on the live queue. Card 2 has a recorded
  GuC lockup history; lane A (cards 0+1) would need lane-A rows (not prepared).
* **Host RAM:** MemAvailable ≥ **105,411,248,128 B** (97 GiB + 1200 MiB, the bundle-8 v5 screen's) +
  the queue's 1 GiB at START; the 2026-10-22 windows measured 120.6–120.7 GB with endpoints stopped.
  Checkpoint host buffers (≤ 94 MB per rank at N = 342) sit inside the supervisor's 8 GiB
  anonymous-memory limit.
* **PAUSE-A stays during the whole window.** Root free ≥ 25 GB + planned writes (34.49 GB free when
  planned). No setting changes.

## What I could not do

* **No device result.** Nothing qualifies the checkpoint, the delta, or the arithmetic of this binary
  on device; the label stays `experimental-two-card`. The device binary was never run on CPU either.
* **Mini CPU sessions have degenerate outputs** (synthetic weights: every token 1, every draft guess 3),
  so CPU token equality is weak evidence; the strong CPU evidence is byte equality of every saved buffer
  and the draft-cache control. The production-shape gate moves no payload (blob bytes are zeros).
* `ops/rehearse_entry.py` keeps two WARN items (no preparation-path probe; unclassified gate-identity
  uses in inherited packet153 files), as packet181/183 did.
* Only the record placement is supported (MTP draft on rank 1, 24/24); other placements are refused at
  save. Only same-binary restores. No ctxkeeper adapter. No batched prefill: appended tokens use the
  engine's incremental prompt step, as on one card.
* The engine reads `rope.bf16` and `mtp-manifest.tsv` from `packet136-record-bundle/` at runtime (the
  `#line` directive keeps `__FILE__` there, exactly as packets 153 and 183); both are content-verified
  at startup and are not pins.
* The inherited packet153 bracket gates (`entry_gate`, `launch_limit_gate`, `worker_gate`,
  `report_gate`) were not re-run: they rehearse the bracket worker/report, which these rows do not use;
  the worker/report rehearsal and the generic entry rehearsal replace them.
* The spare/reserve banks are saved although dead at a boundary (59.2 MB per checkpoint).
* Root-level documents other than this README and `DO-NOT-REPEAT.md` are packet153/136 documents
  carried by the copy (renamed), not packet184 claims.

[Note](../../../../notes/2026-10-22-packet184-twocard-checkpoint.md) · [DO-NOT-REPEAT](DO-NOT-REPEAT.md) ·
[Design](../../SESSION-SWAP-DESIGN.md) · [packet181 (one card)](../packet181-session-swap-v3/README.md)
