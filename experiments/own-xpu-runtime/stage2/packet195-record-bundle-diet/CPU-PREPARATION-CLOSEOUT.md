# Packet195 CPU preparation closeout (2026-10-23)

## Question and identity

Can packet194's exp-diet engine, a screen winner on lane B (slower k3x-diet view 63.413 ≥ 1.005 × every in-load k3x view,
every view exact, +1.96 %, 0.04 points below the +2 % chain bar), be chained as a record bundle on cards 0+1 under the
coordinator's idle-lane ruling and submitted? Identity: Qwen3.8 Flash-Next UD-IQ3_XXS, two B70 cards, single user, greedy,
128-token capped suite, exact vs `iq3-p49-split32-v1`, full BF16 KV; bundle 8 + packet153 static snapshot + V3 head placement
(full target head on rank 1) + k3x (rank 0 holds layers 0-26 and runs GDN layers 24-26 for the verified token,
`kernel_io=kernel`, `rank0_prepare=async`, `boundary_export=copy`) + `expert_gateup=diet` (packet193's exact instruction diet
`p193diet::GateUp` at the 26 + 24 exp-halfcache gate/up sites, bit-identical to the record kernel, 0 B); device binary
`b8482321…` reused byte for byte from packet194 (selection `eb417ec9…`, 20 keys; memory plan `97a76116…`, unchanged).
Coordinator ruling (2026-10-23): "packet194 k3x-diet is a screen winner on 2026-10-23 (lane B, lanequeue-B40, 05:56–06:11
UTC): +1.96 % over every k3x view, every view exact; the +2 % chain bar is missed by 0.04 points, and the lanes are idle,
which the chain policy allows. Derive the record bundle from packet190 with the `k3x-diet` selection and packet194's engine;
prepare a fresh eleven-window chain on cards 0+1; its WS128 must beat 62.345282 (cmvk51wfn001gng01fpbfy89q) and pass every
exactness gate."

## Outcome

CPU preparation is complete and READY was written last; nothing was launched, queued, submitted or committed. The chain has
not run: device correctness, the WS128 rate and any submission are pending. The fresh WS128 must be exact and exceed
62.345282; the packet194 screen plus the ruling admit the chain only. Packet195 was derived from packet190 by
`copy_packet195.py` (938 + 83 files, identity rewrites only) plus exactly the six changes packet194's README prescribes; no
tracked file outside the two new directories and the note was edited, and no packet190/193/194 file was modified. No GPU,
`/dev/dri`, systemd unit, PAUSE/STOP/queue file, sudo or secret was touched; the only systemd calls were the read-only
`list-units`/`show`/`is-active` queries of the unit poll and the launcher's live dry run.

## What worked

- Engines reused byte for byte from packet194's `v5/build`, checked against its build receipt (10 runs, 0 warnings, pinned
  header `aab37609…`, 76 parent objects, 2 replaced) and both device rows; no relink, 0 compiler runs for the engines
  ([inputs/packet194-native.json](../../ops/packet195-orchestration/inputs/packet194-native.json)).
- Production-shape startup of both ranks on the lane-A placement with the k3x-diet selection, every view re-selecting the
  diet: rank 0 census 31,374,119,922 B (90 moved sites, 120 private buffers, 26 diet sites + 1 inert IQ3_S site), rank 1
  31,581,735,626 B (24 diet sites), image 19,025,640 B / 984 extents, 23 native refusals, captures equal packet194's
  diet-first load and differ from the production k3x capture, diet census delta 0 B
  ([real-shape.json](../../ops/packet195-orchestration/evidence/real-shape.json)); k3-state engine transcripts (GNU, Intel)
  equal packet194/189/188's `d451302d…` with copy-engine export runs only and the diet inert-and-counted in the miniature
  ([composition-bytes.json](../../ops/packet195-orchestration/evidence/composition-bytes.json)).
- Chain registration, entry for all 11 windows, the W0p transport canary (266,304 B shared file) and the k3x-diet miniature
  decode identical to bundle 8 through the chain transport (five-layer miniature, 120 fixtures, 28 boundaries), the KD
  reference projection dropping `expert_gateup` with the k3-storage keys
  ([argument-gate.json](../../ops/packet195-orchestration/evidence/argument-gate.json),
  [transport-gate.json](../../ops/packet195-orchestration/evidence/transport-gate.json)).
- s194 screen recomputed from raw tokens, clocks and proposals of packet194 rows 0-1 (126 files pinned in place): slower
  k3x-diet 63.4128, +1.962 % over every k3x view, drift 0.061 %, gate/up saving 10.79 µs/layer (min of both ranks), 78 checks
  exact; the chain rule is recorded as not met (shortfall 0.038 points) and the chain admitted only through
  `policy195.json` `coordinator_idle_lane_exception_authorized` with the ruling quoted
  ([bracket-gate.json](../../ops/packet195-orchestration/evidence/bracket-gate.json)).
- Submission rehearsal: packet136's real evidence replays and the 62.345282 floor refuses it; a tampered output is refused;
  the k3x-diet notes are 1,726 of 2,000 characters and disclose the 128-token capped scope and the bit-identical instruction
  diet; the local `--dry-run` blocks a foreign payload with no key; `--update-record` refuses a non-improving result and
  appends on a scratch ledger only ([cpu-receipts.json](../../ops/packet195-orchestration/cpu-receipts.json)).
- Pin guard: 923 pins, 0 cross-packet mutable, all READY files in the closure
  ([final-pin-guard.json](../../ops/packet195-orchestration/evidence/final-pin-guard.json)); launcher rehearsal
  1 pass + 9 refusals with systemd-run never called
  ([launcher-rehearsal.json](../../ops/packet195-orchestration/evidence/launcher-rehearsal.json)).

## What failed or remains uncertain

- Three harness-shape fixes before the seal (none is an arithmetic finding): the packet `evidence/` directory was excluded
  by the copy and had to exist before `seal195.py`; the orchestration snapshot pins `proposal.jsonl`, so `seal195.py` must
  run again after `make_proposal.py` (the first `check_inputs.py --report` refused with "orchestration snapshot file set
  differs"); packet136's chain output (`packet136-record-bundle/build/device-cards01-a`) was archived off the root disk on
  2026-10-22, so `real_report.py` now replays packet190's record chain (git-ignored `build/device-cards01-p190-a`, read in
  place) and must reproduce 62.345281904743764.
- The chain rule is not met: the screen's +1.96 % is 0.04 points below +2 % and 63.413 is below the 63.592 bar. The chain
  runs on the coordinator's idle-lane ruling; a WS128 at or below 62.345282, or any inexact window, keeps the record at
  packet190 and closes the diet on this line.
- `--server-dry-run` was not run on CPU (it needs the LocalMaxxing key); it is the coordinator's step.
- Root free at seal time was 30.9 GB against the launcher's 28.32 GB floor (25 GB + 3,324,718,708 B of planned writes):
  margin about 2.5 GB. packet190's retained `build/device-cards01-p190-a` (1.2 GB) is now an input of `real_report.py`;
  do not delete it before the chain.
- The private lane plan is informative only ("unsupported; static argv/environment checks only"): the chain is launched by
  `launch_chain.sh`, not as a queue row.

## Evidence and patches

Ops receipts: [ops/packet195-orchestration/evidence/](../../ops/packet195-orchestration/evidence/final-checks.json),
[ready.json](../../ops/packet195-orchestration/ready.json), [README](../../ops/packet195-orchestration/README.md).
Packet: [README.md](README.md), [build-receipt.json](build-receipt.json), [lineage/packet195-copy.json](lineage/packet195-copy.json),
[lineage/packet195-guard-layout.json](lineage/packet195-guard-layout.json), [bundle-selection.json](bundle-selection.json)
(`diet` block). Parent screen: [packet194](../packet194-expert-diet-engine/README.md)
(`v5/evidence/device-row1-bracket-k3x-diet-B-p194/bracket-summary.json`, `s194_decision`; `v5/p194-native.patch`, the pinned
`p193_diet.hpp`). Parent harness: [packet190](../packet190-record-bundle-k3x/README.md). Note:
[notes/2026-10-23-packet195-record-bundle-diet.md](../../../../notes/2026-10-23-packet195-record-bundle-diet.md).

## When to revisit

After the chain: on an exact WS128 above 62.345282, prepare and submit (dry-run, server dry-run, submit, `--update-record`);
on a loss or fault, record the window and the DO-NOT-REPEAT row and keep the record at 62.345282. Revisit the preparation
itself only if a window refuses at launch (argument, transport, KD projection or placement) or the disk floor is not met.
