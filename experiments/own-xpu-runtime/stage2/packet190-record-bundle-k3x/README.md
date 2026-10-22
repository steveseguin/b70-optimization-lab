# Packet190: two-card record bundle, k3x (CPU-prepared, not armed)

**Status (2026-10-22 23:00 UTC): chain run on cards 0+1 (unit `packet190-chain-a`, 22:06-22:53 UTC), all 11 windows passed; WS128 62.345282 tok/s class-balanced, 12/12 exact; submitted and APPROVED as LocalMaxxing `cmvk51wfn001gng01fpbfy89q` (+2.78 % over 60.659520). Chain receipts under `evidence/device-cards01-p190-a/`, bundle under `submission/prepared-a/`, window receipts under `lineage/window-20261022/`. The paragraph below describes the state at the end of CPU preparation.**

**Status at CPU preparation (superseded):** `READY-FOR-DEVICE.json` is written last by
`ops/packet190-orchestration/final_checks.py --ready`. So far:

- no device work has run, and nothing has been queued, armed or submitted;
- no compiler or linker ran for the engines (the only compile was the CPU preparation probe);
- the 60.659520 tok/s record (`cmvjvabyv040jrf01dricuz8s`, packet187) was unchanged at that point (superseded by this packet's `cmvk51wfn001gng01fpbfy89q`).

**Contents.** Packet190 is packet187's record bundle (bundle 8 + packet153 static snapshot + packet186 V3 head
placement) with packet189's **k3x** selection and engine. The selection is packet189's `v5/lineage/k3x/selection.json`,
sha256 `c5443bbfbc88b39fd562956a55ce05667de0781f640fd0cd522a1e5800f392bb` (19 keys). Against packet187's V3 selection
(`923639a9…`) exactly five keys change:

| Key | packet187 (V3) | packet190 (k3x) |
|---|---|---|
| `rank0_layers` | `0-25` | `0-26` (rank 0 also holds GDN layer 26) |
| `boundary` | `rank0` | `rank0-k3` (rank 0 runs layers 24-26 for the verified token; rank 1 from QSA layer 27) |
| `kernel_io` | absent (copy) | `kernel` (small per-interval transfers as kernels) |
| `rank0_prepare` | absent (sync) | `async` (rank-0 half inputs staged without host waits) |
| `boundary_export` | absent (copy) | `copy` (the 20,480-byte boundary export on the copy engine, explicit) |

Head (full 248,320 rows on rank 1), static snapshot, `dense_scales`, `probe` and the draft are unchanged.

**Same as packet189's k3x arm.** Selection, memory plan, dispatch and engines are byte copies:

- `build/device/own-rt-iq3`, sha256 `87eec6453a2a9a9bfe30ed19466c6a70644d9cd168f734be87d2f0a17b776af4`;
- `build/gnu-host/own-rt-iq3`, sha256 `a50588a9e89adacb14cefcc53dd271cbd8054b81fe076dbca81d7b779d99f6c6`;
- `memory-plan.json`, sha256 `97a7611646cdab0d9780166a3a670375a986dcb150cae491c686203eb0fb7d39` (rank 0
  31,374,119,922 B, rank 1 31,581,735,626 B at the production-shape census).

`place_k3x.py` copies them from packet189 `v5/build` and checks them against packet189's build receipt and both
packet189 device rows. They were **reused, not relinked**.

**Chain changes vs packet187** (the six items of packet189's README): selection, engines, memory plan, launcher host
floor 108,797,048,558 B + 1 GiB, KD projection (the k3-storage keys are dropped with `rank0_layers`/`boundary`/
`snapshot_host`), bars (WS128 > 60.659520). Transport size (266,304 B), oracle binding, provenance layout, launcher
refusals and the submission step are packet187's.

**Where things are.**

- Launch procedure, window table, submission commands: [ops README](../../ops/packet190-orchestration/README.md).
- Note: [notes/2026-10-22-packet190-record-bundle-k3x.md](../../../../notes/2026-10-22-packet190-record-bundle-k3x.md).
- Parent screen: [packet189](../packet189-twocard-k3x/README.md); parent harness: [packet187](../packet187-record-bundle-v3/README.md).

## Gates (CPU only; receipts in `ops/packet190-orchestration/evidence/`)

| Gate | Result | Receipt |
|---|---|---|
| Engine placement (reuse, no relink) | device 87eec645… and gnu-host a50588a9… equal packet189's receipt and both device rows; 0 compiler runs | `inputs/packet189-native.json` |
| Unit poll before the compile/heavy steps | `window-*`, `lanequeue-*`, `packet18*`, `packet19*`: none active at 21:49:24Z (the window-p189-driver had ended 21:41Z) | `compile-poll.json` |
| Production-shape startup, both ranks, lane-A placement, k3x selection | rank 0 census 31,374,119,922 B (90 moved/stored sites, 120 private buffers, kio 86,016 B), rank 1 31,581,735,626 B; image 19,025,640 B / 984 extents; every view skips 90 half sites; captures equal packet189's k3x-first | `real-shape.json` |
| k3 state engines, GNU and Intel, k3x selection | canonical transcript `d451302d…` = packet189 = packet188; 149 copy-engine export runs, 0 kernel | `composition-bytes.json` |
| Chain transport and W0p canary (five-layer miniature) | 1000 handovers; old size fails with `shared extent` in both ranks; k3x decode = bundle 8 (24 tokens, 120 fixtures, identical proposals, 28 boundaries) | `transport-gate.json` |
| Real Python entry, all 11 windows, with the K2 replay, oracle and queue loop | pass (125 s) | `argument-gate.json`, `entry190.json` |
| Both-rank preparation probe with real WS128 argv | pass; device totals 31,374,119,922 / 31,581,735,626 B | `preparation.json`, `preparation-build.json` |
| Input closure and drain fix | pass (10,558 static files, 352 write paths) | `input-check.json`, `drain-fix.json` |
| Launch limits | pass | `launch-limits.json` |
| s189 chain rule, recomputed from packet189 rows 0-1 and packet188 row 1 | slower k3x 62.2254 tok/s, +2.657 % over every V3 view (fresh 60.5049), drift 0.283 %, ≥ 61.873; 148 files pinned in place; no kill rule fired | `bracket-gate.json` |
| Entry and report rehearsal (shared checker plus adapter) | pass | `entry-report.json`, `real-report.json` |
| Submission rehearsal | notes 1,508/2,000; floor refuses packet136; tampered output refused; `--dry-run` blocks a foreign payload (rc 2); ledger unchanged | `submission-rehearsal.json` |
| Unit tests (policy, readiness, submission) | 11, 7 and 2 tests OK | `*-tests.log` |
| Seal and CPU receipts | pass | `build-receipt.json`, `cpu-receipts.json` |
| Pin guard and private `lanequeue.py plan --lane A` | 920 pins, 0 cross-packet mutable; plan rc 0 (planned writes 3,324,718,708 B) | `final-checks.json`, `final-pin-guard.json` |
| Guarded launcher rehearsal | 1 pass and 9 refusals in a sandbox, plus one live dry run | `launcher-rehearsal.json` |

## Layout notes

`copy_packet190.py` copied packet187 with identity rewrites only (receipt `lineage/packet190-copy.json`); the six
changes are in `place_k3x.py`, `select_k3x.py`, `bundle_selection.py`, `kd_reference.py`, `build_engine.py` (the
lineage-inputs exclusion in `limits()`), the ops `bracket_gate.py`, `cpu_bytes.py`, `transport_gate.py`,
`preparation_probe.py`, `submission_evidence.py`, `submission_rehearsal.py`, `final_checks.py`, `verify_ready.py`,
`policy190.json`, `launch_chain.sh`, `make_proposal.py`, `compile_poll.py` and the three tests.

`guard_layout190.py` writes `lineage/packet190-guard-layout.json`: `parent-snapshot/`, `calibration/` and
`prefix-calibration/` are symlinks into `lineage-inputs/`; `device/` and `gnu-host/` at the packet root are hard links
of `build/{device,gnu-host}`; the fixture archive and link targets are hard links. `orchestration-snapshot/` holds
byte copies of the ops files the seal pins.
