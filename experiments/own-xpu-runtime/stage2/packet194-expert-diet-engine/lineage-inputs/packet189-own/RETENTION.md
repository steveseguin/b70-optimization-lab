# Packet189 retention

## Tracked (when committed by the coordinator; nothing was committed in preparation)

* **Sources.**
  * The identity-rewritten copy of packet188's harness (`copy_packet189.py`, receipt `lineage/packet189-copy.json`).
  * The packet189 native delta, `v5/k3x-native.patch`: +38 / −15 lines in 6 files, against packet188 after the identity
    rewrite (the `boundary_export` key, the export path selection, `readback(copy_engine)`, the full-shape and state-proof
    hooks).
  * The new and adapted harness: `v5/s189_decision.py` (D from the draft wall, the pinned fresh reference, the five kill
    rules), `v5/test_s189_decision.py` (real packet188/187 data + the synthesis-3 replay), `v5/k3_state_gate.py` (lean
    k3x/k3trims export-identity proof), `v5/make_lineages.py` (19-key selections), the two row configs, `package_rows.py`,
    `check_queue_rows.py` and `final_checks.py`.
* **`analysis/`.** `lever-synthesis-3-20261022.md` and its scripts and outputs (`replay_k3x.py`, `replay-k3x-output.json`,
  `k3x_spread.py`, `k3x-spread-output.json`, `dnr-list.txt`) plus packet188's `replay_v3.py` loader. These are the pricing
  of k3x; the analysis gate and the decision tests re-run the replay.
* **Lineages.** `v5/lineage/{v3,v3k,k3x,k3trims}/`: selections, dispatch, memory plans (one k3 plan, packet188's), screen seals.
* **CPU gate receipts and logs under `v5/evidence/`:**
  * the hashed production-shape archives `shape-*.tar.gz` (16 files);
  * the k3 state transcripts `k3-state-engine-*.txt.gz` and logs (3);
  * `compile-poll.json`;
  * `analysis-real-inputs.json`, the path → sha256 map of the real device files the analysis read in place.
* **`lineage-inputs/`.** packet188's history, hard-linked: zero new bytes. Exceptions:
  * `lineage-inputs/vendor/.../packet58-onecard/suite_driver.py` (the packet identity literal) and `lineage-inputs/queue/*`
    are separate files, so nothing writes through to packet188.
  * `packet188-own/` holds packet188's own certification (README, DO-NOT-REPEAT, RETENTION, READY, proposals, window
    lineage, analysis/) and its small CPU gate receipts; the full-shape, admission and k3-state gates compare against them.

## Not copied (read in place, pinned by hash in `v5/evidence/analysis-real-inputs.json`)

* packet188's device rows: `packet188-twocard-k3-composite/v5/evidence/device-row{0,1,2}-*-B-p188/` (bracket summaries;
  row 2's five views and row 1's view: `receipt.json` and `rank0/timings.jsonl` per prompt). Row 1's summary is also pinned
  in `s189_decision.FRESH_V3` (the fresh V3 reference the decision reads at device time).
* packet187's record chain WS128: `packet187-record-bundle-v3/build/device-cards01-p187-a/WS128/run/repeat-1/*` and
  `evidence/device-cards01-p187-a/WS128/summary.json`.
* The packet49 oracle results (`packet49-integrate/oracle/results/*/result.json`).
* packet186's two incident64 fixtures for `test_analyze.py`.

`final_checks.py` re-hashes every file of the map. If packet188 or packet187 ever moves or cleans these trees, the analysis
gate must be re-run against wherever they are retained; `s189_decision` refuses at device time if packet188 row 1's summary
changes. No device row of this packet reads them except that pinned summary.

## Ignored and local (`/v5/build/`, `/build/`)

* the compiled engines (`device/`, `gnu-host/`) and objects;
* the 78 `inherited/` links to the pinned parent objects;
* the CPU fixtures: full-shape, controller mocks, and the k3 state engines with their pinned miniature selections
  (`build/k3-state/selections/`).

To recreate them, run `nice -n 19 taskset -c 8-15,24-31 python3 -B v5/p189_v5_build_engine.py`. It polls `window-*` and
`lanequeue-*` units first and needs the compilers. Then run `v5/qualify_cpu.py --start full-shape`. The k3 state gate
deletes its raw miniature request trees after writing `k3-state.json`.

The device output directories named in the proposal (`v5/evidence/device-row{0,1}-*-B-p189`) must stay fresh.
