# Packet187 CPU preparation closeout (2026-10-22)

## Question and identity

Can the two-card V3 engine that won packet186's screen (+3.306 % over the split-head bundle-8 controls, every
view exact) be chained as a record bundle on cards 0+1 and submitted? Identity: Qwen3.8 Flash-Next UD-IQ3_XXS,
two B70 cards, single user, greedy, 128-token capped suite, exact vs `iq3-p49-split32-v1`, full BF16 KV; bundle 8 +
V3 (full target head on rank 1, layers 24–25 on rank 0 for the verified token) + packet153 static snapshot;
device binary `693cc194…` reused byte for byte from packet186 (selection `923639a9…`).

## Outcome

CPU preparation is complete and READY was written last; nothing was launched, queued, submitted or committed by
the preparation. The chain has not run: device correctness, the WS128 rate and any submission are pending. The
fresh WS128 must be exact and exceed 58.798109; the packet186 screen admits the chain only.

## What worked

- Engines reused byte for byte from packet186's `v5/build` and checked against its build receipt; no relink, no
  compiler run for either engine ([inputs/packet186-native.json](../../ops/packet187-orchestration/inputs/packet186-native.json)).
- Production-shape startup of both ranks on the lane-A placement, captures equal packet186's V3 arm
  ([real-shape.json](../../ops/packet187-orchestration/evidence/real-shape.json)); state-engine transcripts equal
  packet186 ([composition-bytes.json](../../ops/packet187-orchestration/evidence/composition-bytes.json)).
- Chain registration, entry for all 11 windows, the W0p transport fix (v5 engine's 266,304 B shared file) and the
  KD reference projection ([argument-gate.json](../../ops/packet187-orchestration/evidence/argument-gate.json),
  [transport-gate.json](../../ops/packet187-orchestration/evidence/transport-gate.json)).
- Submission rehearsal: packet136's real evidence replays through the helper and the current floor refuses it; a
  tampered output is refused; the V3 notes are 1,171 of 2,000 characters; `--update-record` refuses a non-improving
  result ([cpu-receipts.json](../../ops/packet187-orchestration/cpu-receipts.json)).
- Pin guard: 917 pins, 0 cross-packet mutable, all READY files in the closure
  ([final-pin-guard.json](../../ops/packet187-orchestration/evidence/final-pin-guard.json)); launcher rehearsal
  1 pass + 9 refusals with systemd-run never called
  ([launcher-rehearsal.json](../../ops/packet187-orchestration/evidence/launcher-rehearsal.json)).

## What failed or remains uncertain

- The first `--ready` run caught a real bug (`verify_ready` compared a tuple against the stored JSON list); READY
  was withdrawn, the check fixed, the packet resealed and rerun.
- `--server-dry-run` was not run on CPU (it needs the LocalMaxxing key); it is the coordinator's step.
- The private lane plan is informative only: the chain is launched directly by `launch_chain.sh`, not as a queue row.
- Four shared submission scripts were dropped from `dependency-pins.json` because the chain never imports them, so
  edits to them no longer make the chain refuse to start.

## Evidence and patches

Ops receipts: [ops/packet187-orchestration/evidence/](../../ops/packet187-orchestration/evidence/final-checks.json),
[ready.json](../../ops/packet187-orchestration/ready.json), [README](../../ops/packet187-orchestration/README.md).
Packet: [README.md](README.md), [build-receipt.json](build-receipt.json), [lineage/packet187-copy.json](lineage/packet187-copy.json).
Parent screen: [packet186](../packet186-twocard-v3/README.md). Note: [notes/2026-10-22-packet187-record-bundle-v3.md](../../../../notes/2026-10-22-packet187-record-bundle-v3.md).

## When to revisit

After the chain: on an exact WS128 above 58.798109, prepare and submit (dry-run, server dry-run, submit,
`--update-record`); on a loss or fault, record the window and the DO-NOT-REPEAT row and keep the record at
58.798109. Revisit the preparation itself only if a window refuses at launch (argument, transport or placement).

## Original preparation note (verbatim)

This replaces the copied packet155 interruption note.

**Status.** CPU preparation for the V3 two-card record chain is complete:

- the ops-side `cpu-receipts.json` passes;
- `final_checks.py` passes;
- the READY markers are written last by `final_checks.py --ready`.

**What was not done.** No GPU, `/dev/dri`, device binary, systemd unit, PAUSE file, STOP file or queue
was touched. No compiler run produced an engine: the engines are packet186's bytes. The only compile was
the CPU preparation probe in `build/preparation187`, built after the compile hold cleared.

**What the chain still has to show.** The chain has not run. Device correctness, the WS128 rate and any
submission are pending. The fresh WS128 must:

- be exact;
- exceed 58.798109.

The packet186 screen (+3.306% over split-head controls) admits the chain only.
