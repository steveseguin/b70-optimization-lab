# Packet58-onecard-cache23-chain CPU preparation closeout (2026-10-23)

## Question and identity

Can the max23 expert-cache capacity that won packet58-onecard-cache23's screen on card 0 (+1.72 % over every warm max
view, fills −12.9 %, 60/60 exact, no kill rule; 2026-10-23 00:57–01:10 UTC) be chained as a one-card record attempt
against 35.926720 tok/s (`cmvjejvoi03qcrf0138emu5a6`)? Identity: Qwen3.8 Flash-Next 125B-A6B UD-IQ3_XXS (the quantized
compressed version), one Arc Pro B70 (card 0, lane A, whole host), single user, greedy, no draft, 128-token capped
suite, exact vs `iq3-p49-split32-v1`, BF16 KV, context 4096, resident lookups, kernel foreground I/O, spin wait; the
packet182c record argv with `--cache-cap max23 --cache-bytes 23049601024` on the packet58-onecard-cache23 engine
`083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a` (reused byte for byte) under that packet's
re-partitioned device plan (bound 29,828,911,360; host 100,487,123,456). The chain bar (+2 %) is not met; the
coordinator admitted the chain under the idle-lanes rule (ruling quoted in README).

## Outcome

CPU preparation is complete and READY was written last by `final_checks.py --ready`; nothing was queued, launched,
submitted or committed; no GPU, `/dev/dri`, systemd unit, PAUSE/STOP/queue file, sudo or secret was touched. The chain
has not run: device exactness, the fresh WS128 rate and any submission are pending. A fresh exact WS128 must exceed
35.92672010504166 and the live ledger; the screen admits the chain only.

## What worked

- Derivation by the shared generator with packet182's two repairs and this packet's capacity hook: the first run
  proved the parent argv is refused by the cache23 host parser ("single admitted maximum allocation required"); the
  second derived a packet that is packet182c-chain byte for byte modulo identity, engine and the four capacity literals
  ([capacity-patch.json](../../ops/packet58c23chain-orchestration/capacity-patch.json),
  [derivation.json](../../ops/packet58c23chain-orchestration/derivation.json)).
- The cache23 delta (40 logged edits: memory plan, admission, validator, tests, engine binding, restore records,
  MEMORY) and its receipts ([cache23-chain-delta.json](evidence/cache23-chain-delta.json)).
- Every model window's native argv carries the two chain flags and the two capacity flags exactly once, in script mode
  and through the real parser ([script-argv-check.json](evidence/script-argv-check.json),
  [chain-flags.json](evidence/chain-flags.json)); pre-device rehearsal 7/7 with the cache23 plan
  ([predevice-cache23.json](evidence/predevice-cache23.json)); the 23 GB plan admits the screen's real post-load census
  ([postnative-cache23.json](evidence/postnative-cache23.json)); queue plan host floor 100,487,123,456
  ([queue-gate.json](evidence/queue-gate.json)).
- The five screen views recomputed from 330 raw files read in place: rates, class medians, drift, gain, exactness,
  fills/token and the DRM peak all equal the screen's summary and decision; lifetime loaded DRM peak 29,988,990,976 B,
  511 MB under the unchanged guard ([admission-gate.json](evidence/admission-gate.json)).
- Python 137 tests OK (9 skipped with reason) after adapting the inherited failure classes that a packet182c scratch
  copy reproduces ([python-cpu-gates-cache23.json](evidence/python-cpu-gates-cache23.json)); submission rehearsal on
  58ad's real evidence, notes 1,936 of 2,000 chars, packet182c's real bundle refused
  ([submission-rehearsal-cache23.json](evidence/submission-rehearsal-cache23.json)).
- Seal 546 sources / 26 gates / 3 artifacts; pin audit 0 parent pins, 0 cross-packet mutable
  ([reseal.json](../../ops/packet58c23chain-orchestration/reseal.json)); final pin census on the READY closure and the
  launcher rehearsal (1 positive dry run + 11 refusals, systemd-run never called)
  ([final-checks.json](evidence/final-checks.json), [final-pin-guard.json](evidence/final-pin-guard.json),
  [launcher-rehearsal.json](evidence/launcher-rehearsal.json)).

## What failed or remains uncertain

- The generator's own post-native rehearsal could only run on packet182c's real chain (21.55 GB arena) with the parent
  plan; the 23 GB plan is rehearsed on the screen's WSCREEN census instead (the only 23 GB device evidence on this host).
- The inherited parent gates (post-load allocation, full-shape submit, resident copies, 58ajb preparation) describe the
  parent harness engine, as they did in packet182c; the cache23 engine's own proofs are provenance records in
  `engine-binding.json`, not re-run here.
- `--server-dry-run` was not run on CPU (it needs the key); it is the coordinator's step. The live launcher `--dry-run`
  is recorded as observed and refuses (rc 4) while the owner endpoints run, as designed.
- The submission notes keep the carried 58ah a/b disclosure in a compacted form (every fact kept) to stay under the
  2,000-character cap; a real run's fault counters move the length by a few characters (64 spare).
- The chain output stays at `evidence/card0-cache23-a` (the harness and validator register it), with the bulky streams
  git-ignored, rather than under `build/`.

## Evidence and patches

Packet: [README.md](README.md), [DO-NOT-REPEAT.md](DO-NOT-REPEAT.md), [RETENTION.md](RETENTION.md),
[MEMORY.md](MEMORY.md), [WINDOW.md](WINDOW.md), [build-receipt.json](build-receipt.json),
[engine-binding.json](engine-binding.json), [derived-chain.json](derived-chain.json), `evidence/*.json`.
Orchestration: [ops/packet58c23chain-orchestration/README.md](../../ops/packet58c23chain-orchestration/README.md)
(derive_cache23_chain.py, apply_cache23_chain_delta.py, cpu_gates.py, admission_gate.py, reseal.py, launch_chain.sh,
final_checks.py, verify_ready.py, prepare_submission.py, submission.py, script_argv_check.py).
Screen: [packet58-onecard-cache23](../packet58-onecard-cache23/README.md). Record line:
[packet182c-chain](../packet182c-chain/README.md). Note:
[notes/2026-10-23-packet58-onecard-cache23-chain.md](../../../../notes/2026-10-23-packet58-onecard-cache23-chain.md).

## When to revisit

After the chain: on an exact WS128 above 35.92672010504166, prepare, local dry run, server dry run, submit once,
`--update-record`; commit the summaries and the submission outputs. On a WS128 at or below the ledger: confirmation
evidence only; record the window and a DO-NOT-REPEAT row; keep the record at 35.926720. On a fault or a DRM-guard
trip: fault-halt rules, no retry, no re-partition without a ruling. Revisit the preparation itself only if a window
refuses at launch (argument, admission, placement) or the live ledger moves before the window.
