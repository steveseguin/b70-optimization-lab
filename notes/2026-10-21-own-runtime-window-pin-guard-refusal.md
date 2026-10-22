# 2026-10-21: approved one-card window did not run; pin-guard refusal of packet178/packet179

## What happened

- 15:42 EDT: the three daily endpoints (`qwen38-27b-fp8` :18130, `qwen38-27b-fp8-tp1-test`
  :18131, `qwen38-27b-vision` :18100) were stopped for an owner-approved device window
  (packet178 rebuilt-binary qualification + packet179 checkpoint restart-and-continue gate).
  Four rows were written into `ops/lane-queue/queue-A.txt` from the two proposals and
  `lanequeue.py run --lane A` was started as a background job of the interactive session.
- No row ever started. `events-A.jsonl` has no START after the 2026-10-19 boundary stop.
  Two independent causes:
  1. `PAUSE-A` (owner pause 2026-10-19T12:02Z) was still present; `boundary()` waits silently
     while it exists.
  2. The runner was a child of the session shell, not a `lanequeue-A<N>` transient unit, and
     died when the session closed.
- Even with those fixed the rows would have been refused before START: the live planner
  (`lanequeue.py plan --lane A`, host-only) fails every row on the pin guard:
  - packet178: 1056 cross-packet mutable pins — `one-card/evidence/build.json`
    `relocated_source_sha256` keyed by the ORIGINAL ancestor paths (packet103/58j/56/165/131/
    97/58g/58ag/75 … trees, 962 entries) plus `native-sequence.json` `sources_sha256` pointing at
    `packet163-full-gate/one-card/native-source` and `build/preparation163/{fixture,probe-main}.cpp`
    (94).
  - packet179: 123 — the same 94 `native-sequence.json` pins plus 29 `checkpoint-probe.json`
    `ancestor_objects_sha256` entries that are symlinked `.o` files under packet58aj
    `frozen-inputs` (ELF, but the "hash-pinned parent binary" exception requires the resolved
    path to stay under that packet's `build/`).
  - Both packets' `check_queue_rows.py` had run `plan` BEFORE `final_checks.py --ready` wrote
    `READY-FOR-DEVICE.json`; its `checks` map is what hash-links the evidence receipts (seal.json
    does not), so the closure the planner checked did not yet include them.
- ~21:50 EDT: found by the next session. Endpoints restored first (fresh state dirs
  `*-20261021-restore3`, same launchers/properties as the 2026-10-20 restoration; receipts in
  `/home/steve/inference/20261021-restore3/`). Packet repairs delegated to two subagents
  (in-packet pin closure, plan after seal, reseal, READY last, packet-only commits).

## Rules reaffirmed

- A window is "running" only when `events-<lane>.jsonl` shows START; report that event.
- Runner = `systemd-run --user --unit=lanequeue-A<N> --working-directory=<repo> python3 -B
  experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py run --lane A`.
- PAUSE files are removed deliberately for an approved window and re-armed afterwards.
- Packet order: gates → package_rows (seal + proposal) → check_queue_rows (plan + rehearse) →
  final_checks → final_checks --ready, with `--ready` re-running the real pin guard on the full
  closure after READY exists; and run the live `plan` before stopping any endpoint.

## packet179 repair (commit 064452363)

- `native_sequence_probe.py` compiles byte-checked private copies under
  `one-card/lineage-inputs/preparation163/` against the packet's own native-source mirror and
  `build/objects`; all 100 pinned sources in-packet; sensor-stream hashes identical to before.
- `checkpoint_probe.py` links dereferenced copies of the 33 ancestor objects from
  `one-card/build/gnu-host-ancestor/` (each checked against packet58aj's build-receipt); probe
  binary, round trip and all six refusals unchanged.
- `check_queue_rows.py` refuses a missing/stale seal or an existing READY; `final_checks.py
  --ready` re-runs the pin guard and withdraws READY on refusal.
- Pre-fix receipts and READY files kept in `one-card/lineage/pinfix-20261021/`.
- Verified by the coordinator: 0 cross-packet pins, both rows plan `passed`, device binary
  8d18538475e00200… unchanged, proposal byte-identical.

## Window result

(filled in below when the window runs)
