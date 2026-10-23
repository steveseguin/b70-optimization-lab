# Packet191 retention

## Tracked (when committed by the coordinator; nothing was committed in preparation)

* **Sources.**
  * The identity-rewritten copy of packet189's harness (`copy_packet191.py`, receipt `lineage/packet191-copy.json`).
  * The packet191 native delta, `v5/sites-native.patch` (+69 / −17 lines in 8 files, against packet189 after the identity
    rewrite): the site recorder `v5/native/p191_sites.hpp` (new, 31 lines), `main.cpp` (finish() retains sampled events,
    `attribution_row` writes `packet191.site.v1`), `rank.hpp` (half phase/corrected tag), `engine_bracket.hpp` (the `sites`
    key: domain, in-load switch, `sites_on`), `v3_boundary.hpp` (boundary phase tag), `p49d_submit.cpp` (the key; 19/20-key
    k3-storage selections), and the two CPU fixtures (`full_shape_entry.cpp`: sites flag, refusal, format proof;
    `v3_state.cpp`: sites flag and row counter in the result).
  * The new and adapted harness: `v5/s191_report.py` (the attribution and the report), `v5/test_s191_report.py` (real
    packet189/190 data, the engine's row format, synthetic instrumented views on packet110's call times), `v5/analysis_gate.py`,
    `v5/make_lineages.py` (the two 20-key lineages), the two row configs, `v5/bracket_config.py`, `v5/bracket.py`,
    `v5/analyze.py`, `v5/p191_v5_compare.py` (sites census per view, off/on bracket fields), `v5/p191_v5_full_shape.py`
    (sites loads, format proof), `v5/k3_state_gate.py` (k3x / k3x-off / k3x-on identity), `v5/admission_gate.py`,
    `v5/cpu_seal.py`, `v5/p191_v5_queue_plan.py`, `package_rows.py`, `check_queue_rows.py`, `final_checks.py`.
* **`analysis/`.** `dnr-list.txt`, `dnr-count.txt` and `dnr-class-grep.txt`: the DO-NOT-REPEAT corpus grep for every class
  family the report can flag (the closures `s191_report.CLOSURES` quotes).
* **Lineages.** `v5/lineage/{v3,v3k,k3x,k3trims,k3x-off,k3x-on}/`: selections, dispatch, memory plans (one k3 plan,
  packet188's), screen seals.
* **CPU gate receipts and logs under `v5/evidence/`:**
  * the hashed production-shape archives `shape-*.tar.gz` (24 files: 12 loads × 2 ranks; the sites loads carry the
    engine-written `packet191.site.v1` format-proof rows under `view*/sites.jsonl`);
  * the k3 state transcripts `k3-state-engine-*.txt.gz` and logs (4: GNU k3x / k3x-off / k3x-on, Intel k3x-on);
  * `compile-poll.json`;
  * `analysis-real-inputs.json`, the path → sha256 map of the real device files and the two references the analysis read
    in place.
* **`lineage-inputs/`.** packet189's history, hard-linked: zero new bytes (1,517 links). Exceptions:
  * `lineage-inputs/vendor/.../packet58-onecard/suite_driver.py` (the packet identity literal) and `lineage-inputs/queue/*`
    are separate files, so nothing writes through to packet189.
  * `packet189-own/` holds packet189's own certification (README, DO-NOT-REPEAT, RETENTION, READY, proposals, analysis/, the
    window lineage) and its small CPU gate receipts; `packet188-own/` stays as packet189 carried it (the full-shape, admission
    and k3-state gates still compare against packet188's receipts: the storage is unchanged).

## Not copied (read in place, pinned by hash in `v5/evidence/analysis-real-inputs.json`)

* packet189's device rows: `packet189-twocard-k3x/v5/evidence/device-row{0,1}-*-B-p189/` (bracket summaries; row 1's two
  k3x views: `receipt.json`, `rank0/timings.jsonl`, `rank1/timings.jsonl`, `rank1/draft-rows.jsonl` per prompt), the
  k3x-first production-shape archives (the launch label census).
* packet190's record chain WS128: `packet190-record-bundle-k3x/build/device-cards01-p190-a/WS128/run/repeat-1/*/receipt.json`
  and `evidence/device-cards01-p190-a/WS128/run/summary.json`.
* packet110's `roofline.json`, packet77's `byte_formulas.py`, packet72's `header-census.json` (the floor and comparison
  references; `s191_report` pins them by sha256 at every use).
* The packet49 oracle results (`packet49-integrate/oracle/results/*/result.json`) and packet186's two incident64 fixtures.

`final_checks.py` re-hashes every file of the map; `s191_report` refuses at device time if a pinned reference changed.
No device row of this packet reads them except through the report.

## Ignored and local (`/v5/build/`, `/build/`)

* the compiled engines (`device/`, `gnu-host/`) and objects;
* the 78 `inherited/` links to the pinned parent objects;
* the CPU fixtures: full-shape, controller mocks, and the k3 state engines with their pinned miniature selections.

To recreate them, run `nice -n 19 taskset -c 8-15,24-31 python3 -B v5/p191_v5_build_engine.py`. It polls `window-*` and
`lanequeue-*` units first and needs the compilers. Then run `v5/qualify_cpu.py --start full-shape`. The k3 state gate
deletes its raw miniature request trees after writing `k3-state.json`.

The device output directories named in the proposal (`v5/evidence/device-row{0,1}-*-B-p191`) must stay fresh.
