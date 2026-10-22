# Packet190 CPU preparation closeout (2026-10-22)

## Question and identity

Can packet189's k3x engine, which met the chain rule on lane B (slower k3x view 62.225 tok/s ≥ 1.02 × every V3 view
and ≥ 61.873; every view exact), be chained as a record bundle on cards 0+1 and submitted? Identity: Qwen3.8
Flash-Next UD-IQ3_XXS, two B70 cards, single user, greedy, 128-token capped suite, exact vs `iq3-p49-split32-v1`, full
BF16 KV; bundle 8 + packet153 static snapshot + V3 head placement (full target head on rank 1) + k3x (rank 0 holds
layers 0-26 and runs GDN layers 24-26 for the verified token, `kernel_io=kernel`, `rank0_prepare=async`,
`boundary_export=copy`); device binary `87eec645…` reused byte for byte from packet189 (selection `c5443bbf…`, memory
plan `97a76116…`). Coordinator ruling (2026-10-22): "Packet189 k3x met the chain rule on 2026-10-22 (lane B,
lanequeue-B36, 21:17–21:32 UTC): slower k3x view 62.225 ≥ 1.02 × every V3 view and ≥ 61.873. Derive the record bundle
from packet187 exactly as packet189's README prescribes and prepare a fresh eleven-window chain on cards 0+1; the
chain's WS128 must beat 60.659520 (cmvjvabyv040jrf01dricuz8s) and pass every exactness gate."

## Outcome

CPU preparation is complete and READY was written last; nothing was launched, queued, submitted or committed. The
chain has not run: device correctness, the WS128 rate and any submission are pending. The fresh WS128 must be exact
and exceed 60.659520; the packet189 screen admits the chain only. Packet190 was derived from packet187 by
`copy_packet190.py` (938 + 83 files, identity rewrites only) plus exactly the six changes packet189's README
prescribes; no tracked file outside the two new directories and the note was edited.

## What worked

- Engines reused byte for byte from packet189's `v5/build`, checked against its build receipt and both device rows;
  no relink, 0 compiler runs for the engines
  ([inputs/packet189-native.json](../../ops/packet190-orchestration/inputs/packet189-native.json)).
- Production-shape startup of both ranks on the lane-A placement with the k3x selection: rank 0 census
  31,374,119,922 B (90 moved sites, 120 private buffers), rank 1 31,581,735,626 B, image 19,025,640 B / 984 extents,
  captures equal packet189's k3x-first ([real-shape.json](../../ops/packet190-orchestration/evidence/real-shape.json));
  k3-state engine transcripts equal packet189/188's `d451302d…` with copy-engine export runs only
  ([composition-bytes.json](../../ops/packet190-orchestration/evidence/composition-bytes.json)).
- Chain registration, entry for all 11 windows, the W0p transport canary (266,304 B shared file) and the k3x
  miniature decode identical to bundle 8 through the chain transport (five-layer miniature, 120 fixtures), the KD
  reference projection dropping the k3-storage keys
  ([argument-gate.json](../../ops/packet190-orchestration/evidence/argument-gate.json),
  [transport-gate.json](../../ops/packet190-orchestration/evidence/transport-gate.json)).
- s189 chain rule recomputed from raw tokens, clocks and proposals of packet189 rows 0-1 and packet188 row 1 (148
  files pinned in place): slower k3x 62.2254, +2.657 % over every V3 view, drift 0.283 %, no kill rule fired
  ([bracket-gate.json](../../ops/packet190-orchestration/evidence/bracket-gate.json)).
- Submission rehearsal: packet136's real evidence replays and the 60.659520 floor refuses it; a tampered output is
  refused; the k3x notes are 1,508 of 2,000 characters; the local `--dry-run` blocks a foreign payload with no key;
  `--update-record` refuses a non-improving result and appends on a scratch ledger only
  ([cpu-receipts.json](../../ops/packet190-orchestration/cpu-receipts.json)).
- Pin guard: 920 pins, 0 cross-packet mutable, all READY files in the closure
  ([final-pin-guard.json](../../ops/packet190-orchestration/evidence/final-pin-guard.json)); launcher rehearsal
  1 pass + 9 refusals with systemd-run never called
  ([launcher-rehearsal.json](../../ops/packet190-orchestration/evidence/launcher-rehearsal.json)).

## What failed or remains uncertain

- Three harness-shape refusals were fixed before the seal (none is an arithmetic finding): `build_engine.limits()`
  counted the guard-layout hard links as build bytes (packet187 had compiled its probe before applying the layout);
  the chain's four-layer miniature cannot host `rank0_layers=0-26`, so the transport decode uses packet189's
  five-layer `--pipeline-mini5` for the reference and k3x alike; the rounded record 60.659520 is 8e-8 above the
  ledger's 60.65951991975228, so the hard floor is the rounded figure (a WS128 of exactly 60.659520 is refused).
- `--server-dry-run` was not run on CPU (it needs the LocalMaxxing key); it is the coordinator's step.
- Root free at seal time was 28.35 GB against the launcher's 28.32 GB floor (25 GB + 3,324,718,708 B of planned
  writes): the disk margin is about 30-100 MB. Free space (packet187's retained `build/device-cards01-p187-a`,
  1.3 GB, or other scratch) before launching.
- The private lane plan is informative only ("unsupported; static argv/environment checks only"): the chain is
  launched by `launch_chain.sh`, not as a queue row.

## Evidence and patches

Ops receipts: [ops/packet190-orchestration/evidence/](../../ops/packet190-orchestration/evidence/final-checks.json),
[ready.json](../../ops/packet190-orchestration/ready.json), [README](../../ops/packet190-orchestration/README.md).
Packet: [README.md](README.md), [build-receipt.json](build-receipt.json), [lineage/packet190-copy.json](lineage/packet190-copy.json),
[lineage/packet190-guard-layout.json](lineage/packet190-guard-layout.json). Parent screen:
[packet189](../packet189-twocard-k3x/README.md) (`v5/evidence/device-row1-bracket-v3k-k3x-B-p189/bracket-summary.json`,
`s189_decision`). Parent harness: [packet187](../packet187-record-bundle-v3/README.md). Note:
[notes/2026-10-22-packet190-record-bundle-k3x.md](../../../../notes/2026-10-22-packet190-record-bundle-k3x.md).

## When to revisit

After the chain: on an exact WS128 above 60.659520, prepare and submit (dry-run, server dry-run, submit,
`--update-record`); on a loss or fault, record the window and the DO-NOT-REPEAT row and keep the record at
60.659520. Revisit the preparation itself only if a window refuses at launch (argument, transport, KD projection or
placement) or the disk floor is not met.
