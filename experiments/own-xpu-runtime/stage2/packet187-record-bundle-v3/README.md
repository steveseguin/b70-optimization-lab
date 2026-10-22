# Packet187: two-card record bundle, V3 (CPU-prepared, not armed)

**Status: CPU preparation complete.** `READY-FOR-DEVICE.json` is written last by
`ops/packet187-orchestration/final_checks.py --ready`. So far:

- no device work has run, and nothing has been queued, armed or submitted;
- no compiler or linker ran;
- the 58.798109 tok/s record (`cmve4dtir007wrf01k57sdf23`) is unchanged.

**Contents.** Packet187 is bundle 8 (packet136's record selection) plus two changes. The rest of the
selection is bundle 8's (`selection.json`, sha256 `923639a9c03fe8b5...`; 16 keys).

- **Packet153's static snapshot:** `snapshot_host=static`, `probe=off`, `dense_scales=expanded`.
- **Packet186's V3 verified-boundary rebalance:** `rank0_layers=0-25`, `boundary=rank0`. Rank 1 keeps
  the full target head. Rank 0 runs layers 24-25 for the verified token, and rank 1 starts at layer 26.

**Same as packet186's V3 arm.** The selection, memory plan, dispatch and engine are identical:

- `build/device/own-rt-iq3`, sha256 `693cc194bb577cd20f95e63f06bf6e463074944e2d1193f8c3ed1a8a4528d739`;
- `build/gnu-host/own-rt-iq3`, sha256 `9035149a...`.

Both are byte copies of packet186's `v5/build` engines, made by `place_v3.py` and checked against
packet186's build receipt and every packet186 device row. They were **reused, not relinked**.

**Chain changes.** The chain is packet136/155's eleven-window harness with three changes:

1. **Transport size.** The transport's shared file is the engine's 266,304 B. Packet155's chain died in
   W0p on `shared extent` with 200,704 B.
2. **KD.** KD's layer-streaming reference projects the V3 keys away (`rank0_layers=0-23`,
   `boundary=none`, `snapshot_host=production`).
3. **Provenance layout.** Provenance lives under `lineage-inputs/`, following packet143's layout, so the
   live lane-queue pin guard sees 0 cross-packet mutable pins.

**Where things are.**

- Launch procedure, window table with expected durations, and submission commands:
  [ops README](../../ops/packet187-orchestration/README.md).
- Note: [notes/2026-10-22-packet187-record-bundle-v3.md](../../../../notes/2026-10-22-packet187-record-bundle-v3.md).

## Gates (CPU only; receipts in `ops/packet187-orchestration/evidence/`)

| Gate | Result | Receipt |
|---|---|---|
| Engine placement (reuse, no relink) | device 693cc194… and gnu-host 9035149a… equal packet186's receipt; 0 compiler runs | `inputs/packet186-native.json` |
| Compile hold (`window-p186-driver`) | active 16:30-16:44Z, inactive 16:45Z; the preparation probe was built after it | `compile-poll.json`, `preparation-build.json` |
| Production-shape startup, both ranks, lane A placement | rank 0 census 30,245,049,064 B, rank 1 31,581,735,626 B; image 19,025,640 B / 984 extents; 60 moved sites; captures equal packet186's V3 | `real-shape.json` |
| V3 state engines, GNU and Intel | transcripts equal packet186's | `composition-bytes.json` |
| Chain transport and W0p canary | 1000 handovers; the old size fails with `shared extent` in both ranks; V3 decode = bundle 8 | `transport-gate.json` |
| Real Python entry, all 11 windows, with the K2 replay, oracle and queue loop | pass | `argument-gate.json`, `entry187.json` |
| Both-rank preparation probe with real WS128 argv | pass | `preparation.json` |
| Input closure and drain fix | pass | `input-check.json`, `drain-fix.json` |
| Launch limits | pass | `launch-limits.json` |
| s186 chain rule, recomputed from packet186's raw rows | V3 min 60.5326 tok/s, +3.306% over split controls, ≥59.974; 169 files pinned in place | `bracket-gate.json` |
| Entry and report rehearsal (shared checker plus adapter) | pass | `entry-report.json`, `real-report.json` |
| Submission rehearsal | see the ops README | `submission-rehearsal.json` |
| Unit tests (policy, readiness, submission) | 11, 7 and 2 tests OK | `*-tests.log` |
| Seal and CPU receipts | pass | `build-receipt.json`, `cpu-receipts.json` |
| Pin guard and private `lanequeue.py plan --lane A` | 0 cross-packet mutable pins; plan rc 0 (planned writes 3,324,718,708 B) | `final-checks.json`, `final-pin-guard.json` |
| Guarded launcher rehearsal | 1 pass and 9 refusals in a sandbox, plus one live dry run | `launcher-rehearsal.json` |

## Layout notes

`guard_layout187.py` writes `lineage/packet187-guard-layout.json`. It made these changes:

- `parent-snapshot/`, `calibration/` and `prefix-calibration/` are now symlinks into `lineage-inputs/`.
- Packet75's chain binding and packet136's eleven chain `window.json` receipts are byte copies under
  `lineage-inputs/`.
- The fixture archive and fixture link targets are hard links, so they use no new disk.
- `device/` and `gnu-host/` at the packet root are hard links of `build/{device,gnu-host}`. The seal's
  build-relative artifact names resolve there for the guard; `chain_seal.py` checks that the inodes match.

The `orchestration-snapshot/` directory holds byte copies of the ops files that the seal pins.
