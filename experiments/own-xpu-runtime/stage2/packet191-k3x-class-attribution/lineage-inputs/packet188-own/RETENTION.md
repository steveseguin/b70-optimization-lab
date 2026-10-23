# Packet188 retention

## Tracked (when committed by the coordinator; nothing was committed in preparation)

* **Sources.**
  * The identity-rewritten copy of packet186's harness (`copy_packet188.py`, receipt `lineage/packet188-copy.json`).
  * The packet188 native delta, `v5/k3-native.patch`: +298 / −67 lines in 11 files, against packet186 after the identity
    rewrite.
  * The new and adapted harness: `v5/k3_state_gate.py`, `v5/s188_decision.py`, `v5/test_s188_decision.py`,
    `v5/make_lineages.py`, the row configs, `package_rows.py`, `check_queue_rows.py` and `final_checks.py`.
* **`analysis/`.** `lever-synthesis-2-20261022.md` and its scripts and outputs (`replay_v3.py`, `price_v3_levers.py`,
  `composites.py`, `collect_dnr.sh`, `replay-p187.json`, `price-v3-output.json`, `composites-output.json`,
  `dnr-list.txt`). These are the pricing of this composite.
* **Lineages.** `v5/lineage/{v3,v3k,k3trims,k3,k3kio,k3prep}/`: selections, dispatch, memory plans, screen seals.
* **CPU gate receipts and logs under `v5/evidence/`:**
  * the hashed production-shape archives `shape-*.tar.gz` (22 files);
  * the k3 state transcripts `k3-state-engine-*.txt.gz` and logs;
  * `compile-poll.json`;
  * `analysis-real-inputs.json`, the path → sha256 map of the 93 real device files the analysis read in place.
* **`lineage-inputs/`.** packet186's history, hard-linked: zero new bytes. Exceptions:
  * `lineage-inputs/queue/*` and `lineage-inputs/vendor/.../packet58-onecard/suite_driver.py` are separate files, so
    nothing writes through to packet186. The suite driver carries the packet188 identity literal.
  * `packet186-own/` holds packet186's own certification and its small CPU gate receipts.

## Not copied (read in place, pinned by hash in `v5/evidence/analysis-real-inputs.json`)

* packet186's device rows: `packet186-twocard-v3/v5/evidence/device-row{0,2}-*-B-p186/` (bracket and smoke summaries,
  the V3 view receipts and `rank0/timings.jsonl` streams).
* packet187's record chain WS128: `packet187-record-bundle-v3/build/device-cards01-p187-a/WS128/run/repeat-1/*` and
  `evidence/device-cards01-p187-a/WS128/summary.json`.
* The packet49 oracle results (`packet49-integrate/oracle/results/*/result.json`).

`final_checks.py` re-hashes all 93 files. If packet186 or packet187 ever moves or cleans these trees, the analysis gate
must be re-run against wherever they are retained. The device rows of this packet do not read them.

## Ignored and local (`/v5/build/`, `/build/`)

* the compiled engines (`device/`, `gnu-host/`) and objects;
* the 78 `inherited/` links to the pinned parent objects;
* the CPU fixtures: full-shape, controller mocks, and the k3 state engines with their pinned miniature selections
  (`build/k3-state/selections/`).

To recreate them, run `nice -n 19 taskset -c 8-15,24-31 python3 -B v5/p188_v5_build_engine.py`. It polls `window-*`
units first and needs the compilers. Then run `v5/qualify_cpu.py --start full-shape`. The k3 state gate deletes its raw
miniature request trees after writing `k3-state.json`.

The device output directories named in the proposal (`v5/evidence/device-row{0..2}-*-B-p188`) must stay fresh.
