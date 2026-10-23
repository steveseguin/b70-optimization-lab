# Packet195: two-card record bundle, k3x-diet (CPU-prepared, not armed)

**Status (2026-10-23 07:40 UTC): chain run on cards 0+1 (unit `packet195-chain-a`, 06:43-07:31 UTC), all 11 windows passed; WS128 63.611824 tok/s class-balanced, 12/12 exact; submitted and APPROVED as LocalMaxxing `cmvkniuvp003gng017f0s68rn` (+2.03 % over 62.345282). Chain receipts under `evidence/device-cards01-p195-a/`, bundle under `submission/prepared-a/`, window receipts under `lineage/window-20261023/`.**

**Status (2026-10-23 06:40 UTC, CPU preparation):** `READY-FOR-DEVICE.json` is written last by
`ops/packet195-orchestration/final_checks.py --ready`. So far:

- no device work has run, and nothing has been queued, armed, submitted or committed;
- no compiler or linker ran for the engines (the only compile was the CPU preparation probe, after the unit poll);
- the 62.345282 tok/s record (`cmvk51wfn001gng01fpbfy89q`, packet190) is unchanged.

**Contents.** Packet195 is packet190's record bundle (bundle 8 + packet153 static snapshot + packet186 V3 head placement +
packet189 k3x) with packet194's **k3x-diet** selection and engine. The selection is packet194's `v5/lineage/k3x-diet/selection.json`,
sha256 `eb417ec915821def1ccfa9ecaf87851ee81846097d489ba52196f63d551a50ac` (20 keys). Against packet190's k3x selection
(`c5443bbf…`, 19 keys) exactly one key is added:

| Key | packet190 (k3x) | packet195 (k3x-diet) |
|---|---|---|
| `expert_gateup` | absent (= `production`: `p90exp::Kernel<IQ2_S,2560,64,false,true>`) | `diet` (`p193diet::GateUp`, packet193's exact instruction diet of the same kernel: same loads, same FP32 operation order, sign applied after the scale multiply, exceptional test hoisted per 256-weight step; bit-identical outputs on both CPU host twins, in the random stress and on device) |

It applies at the exp-halfcache (IQ2_S) gate/up sites: 26 on rank 0 (the IQ3_S p28 gate/up layer keeps its kernel, counted as
1 inert site) and 24 on rank 1. Head (full 248,320 rows on rank 1), static snapshot, k3 boundary `rank0-k3` with layers 24-26
on rank 0, `kernel_io=kernel`, `rank0_prepare=async`, `boundary_export=copy`, `dense_scales`, `probe` and the draft are
unchanged. The diet adds **0 B** of allocation per rank (packet194 full-shape census; reproduced here).

**Same as packet194's k3x-diet arm.** Selection, memory plan, dispatch and engines are byte copies:

- `build/device/own-rt-iq3`, sha256 `b8482321769039274daf42b70f783517177cbc8c1d0b2d81b8ebab25f1442bdc`;
- `build/gnu-host/own-rt-iq3`, sha256 `5d8f3c057ccbe2214da30bbf98f656f23d63653db328c64102cfdf59425720db`;
- `memory-plan.json`, sha256 `97a7611646cdab0d9780166a3a670375a986dcb150cae491c686203eb0fb7d39` (packet188/189's k3 ledger,
  unchanged from packet190: rank 0 31,374,119,922 B, rank 1 31,581,735,626 B at the production-shape census).

`place_diet.py` copies the engines from packet194 `v5/build` and checks them against packet194's build receipt (10 compiler
runs, 0 warnings, pinned header `aab37609…`, 76 parent objects, 2 replaced) and both packet194 device rows. They were
**reused, not relinked**.

**Chain changes vs packet190** (the six items of packet194's README): selection, engines, memory plan (unchanged, stated with
packet194's census), launcher host floor 108,797,048,558 B + 1 GiB (unchanged), KD projection (`expert_gateup` is dropped with
the k3-storage keys `kernel_io`/`rank0_prepare`/`boundary_export` and `rank0_layers`/`boundary`/`snapshot_host`), bars
(WS128 > 62.345282). Transport size (266,304 B), oracle binding, provenance layout, launcher refusals and the submission step
are packet190's.

**Where things are.**

- Launch procedure, window table, submission commands: [ops README](../../ops/packet195-orchestration/README.md).
- Note: [notes/2026-10-23-packet195-record-bundle-diet.md](../../../../notes/2026-10-23-packet195-record-bundle-diet.md).
- Parent screen: [packet194](../packet194-expert-diet-engine/README.md); parent harness: [packet190](../packet190-record-bundle-k3x/README.md).

## Gates (CPU only; receipts in `ops/packet195-orchestration/evidence/`)

| Gate | Result | Receipt |
|---|---|---|
| Engine placement (reuse, no relink) | device b8482321… and gnu-host 5d8f3c05… equal packet194's receipt and both device rows; pinned diet header aab37609…; 0 compiler runs | `inputs/packet194-native.json` |
| Unit poll before the compile/heavy steps | `window-*`, `lanequeue-*`, `packet*`: none active at 06:27:01Z (the owner's `window-p194b-driver …-restore21` had ended; endpoint-restore windows are tolerated by the poll) | `compile-poll.json` |
| Production-shape startup, both ranks, lane-A placement, k3x-diet selection (every view re-selects the diet) | rank 0 census 31,374,119,922 B (90 moved/stored sites, 120 private buffers, kio 86,016 B, 26 diet sites + 1 inert), rank 1 31,581,735,626 B (24 diet sites); image 19,025,640 B / 984 extents; 23 native refusals; every view skips 90 half sites; captures equal packet194's diet-first load and differ from the production k3x capture; diet census delta 0 B | `real-shape.json` |
| k3 state engines, GNU and Intel, k3x-diet selection | canonical transcript `d451302d…` = packet194 = packet189 = packet188; 149 copy-engine export runs, 0 kernel; the diet is inert and counted in the miniature (0 diet sites, 4 inert) | `composition-bytes.json` |
| Chain transport and W0p canary (five-layer miniature) | 1000 handovers; old size fails with `shared extent` in both ranks; k3x-diet decode = bundle 8 (24 tokens, 120 fixtures, identical proposals, 28 boundaries) | `transport-gate.json` |
| Real Python entry, all 11 windows, with the K2 replay, oracle and queue loop | pass | `argument-gate.json`, `entry195.json` |
| Both-rank preparation probe with real WS128 argv | pass; device totals 31,374,119,922 / 31,581,735,626 B | `preparation.json`, `preparation-build.json` |
| Input closure and drain fix | pass (10,564 static files, 352 write paths) | `input-check.json`, `drain-fix.json` |
| Launch limits | pass | `launch-limits.json` |
| s194 screen, recomputed from packet194 rows 0-1 | slower k3x-diet 63.4128 tok/s, +1.962 % over every k3x view (fastest 62.1927), drift 0.061 %, gate/up saving 10.79 µs/layer (min of both ranks), 78 checks exact; chain rule NOT met (shortfall 0.038 points), admitted by the coordinator idle-lane ruling; 126 files pinned in place; no kill rule fired | `bracket-gate.json` |
| Entry and report rehearsal (shared checker plus adapter; packet190's record chain replayed, 62.345281904743764 reproduced) | pass | `entry-report.json`, `real-report.json` |
| Submission rehearsal | notes 1,726/2,000 (128-token capped scope and the bit-identical diet kernel disclosed); 62.345282 floor refuses packet136; tampered output refused; `--dry-run` blocks a foreign payload (rc 2); ledger unchanged | `submission-rehearsal.json` |
| Unit tests (policy, readiness, submission) | 11, 8 and 2 tests OK | `*-tests.log` |
| Seal and CPU receipts | pass | `build-receipt.json`, `cpu-receipts.json` |
| Pin guard and private `lanequeue.py plan --lane A` | 923 pins, 0 cross-packet mutable; plan rc 0 (planned writes 3,324,718,708 B) | `final-checks.json`, `final-pin-guard.json` |
| Guarded launcher rehearsal | 1 pass and 9 refusals in a sandbox, plus one live dry run | `launcher-rehearsal.json` |

## Layout notes

`copy_packet195.py` copied packet190 with identity rewrites only (receipt `lineage/packet195-copy.json`: 938 + 83 files, 26 + 37
rewritten); the six changes are in `place_diet.py`, `select_diet.py`, `bundle_selection.py`, `kd_reference.py`, `chain_seal.py`,
`reuse_build.py`, `guard_layout195.py`, the ops `bracket_gate.py`, `cpu_bytes.py`, `transport_gate.py`, `preparation_probe.py`,
`submission_evidence.py`, `submission_rehearsal.py`, `final_checks.py`, `verify_ready.py`, `policy195.json`, `launch_chain.sh`,
`make_proposal.py`, `seal195.py`, `compile_poll.py`, `real_report.py` and the three tests.

`guard_layout195.py` writes `lineage/packet195-guard-layout.json`: `parent-snapshot/`, `calibration/` and
`prefix-calibration/` are symlinks into `lineage-inputs/`; `device/` and `gnu-host/` at the packet root are hard links
of `build/{device,gnu-host}`; the fixture archive and link targets are hard links. `orchestration-snapshot/` holds
byte copies of the ops files the seal pins. Copied scripts whose docstrings still say "Packet190"/"Packet187" (capitalised,
outside the identity rewrite) describe inherited mechanics, not this packet's identity.
