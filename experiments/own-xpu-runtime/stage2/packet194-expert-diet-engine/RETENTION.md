# Packet194 retention

## Tracked (when committed by the coordinator; nothing was committed in preparation)

* **Sources.**
  * The identity-rewritten copy of packet189's harness (`copy_packet194.py`, receipt `lineage/packet194-copy.json`).
  * The packet194 native delta, `v5/p194-native.patch`: +57 / −16 lines in 7 files against packet189 after the identity
    rewrite (the `expert_gateup` key, Arm 13 and the six-argument dispatch, the 20-key parser, the full-shape and
    state-proof hooks), plus the pinned packet193 header `native-base/…/p193_diet.hpp` (byte copy, sha256 `aab37609…`) and
    the new CPU fixture `v5/native/diet_fixture.cpp`.
  * The new and adapted harness: `v5/p194_v5_build_engine.py` (four TUs, unit poll with endpoint-restore tolerance),
    `v5/kernel_identity.py`, `v5/diet_fixture_gate.py`, `v5/k3_state_gate.py`, `v5/p194_v5_full_shape.py` (diet loads and
    launch census), `v5/s194_decision.py`, `v5/test_s194_decision.py`, `v5/analysis_gate.py`, `v5/make_lineages.py` (20-key
    selections), `v5/bracket_config.py`, `v5/bracket.py`, `v5/analyze.py`, `v5/test_analyze.py`, the two row configs,
    `v5/p194_v5_queue_plan.py`, `v5/run_chain.sh`, `package_rows.py`, `check_queue_rows.py` and `final_checks.py`.
* **`analysis/`.** `dnr-grep.txt` (the 322-file DO-NOT-REPEAT search).
* **Lineages.** `v5/lineage/{v3,v3k,k3x-record,k3x,k3x-diet}/`: selections, dispatch, memory plans (one k3 plan,
  packet188/189's), screen seals.
* **CPU gate receipts and logs under `v5/evidence/`:** `build.json`, `compile-poll.json`, `kernel-identity.json`,
  `diet-fixture.json` + `diet-fixture-{GNU,Intel}.log`, `full-shape.json` + the hashed production-shape archives
  `shape-*.tar.gz`, `k3-state.json` + `k3-state-engine-*.{log,txt.gz}`, `admission.json`, `analysis.json`,
  `analysis-real-inputs.json` (the path → sha256 map of the real device files the analysis read in place), the analysis
  test logs, `controller.json`, `safety.json`, `exec-limits.json`, `loader.json`, `cpu-seal.json`, `package-rows.json`,
  `check-queue-rows.json`, `queue-plan.json`, `plan-B.log`, `rehearse.json`, `entry-gate.json`, `launch-limits.json`,
  `worker-gate.json`, `report-gate.json`, `pin-guard.json`, `final-checks.json`, `final-pin-guard.json`, the `qualify-*.log`
  chain logs and `chain.log`, and `READY-FOR-DEVICE.json`.
* **`lineage-inputs/`.** packet189's history, hard-linked: zero new bytes, except
  `lineage-inputs/vendor/.../packet58-onecard/suite_driver.py` (the packet identity literal; a separate file).
  `packet189-own/` holds packet189's own certification (README, DO-NOT-REPEAT, RETENTION, READY, proposals, window lineage,
  analysis/, copy script) and its small CPU gate receipts; the full-shape, admission and k3-state gates compare against them.

## Not copied (read in place, pinned by hash in `v5/evidence/analysis-real-inputs.json`)

* packet189's device rows: `packet189-twocard-k3x/v5/evidence/device-row{0,1}-*-B-p189/` (bracket summaries; row 1's five
  views: `receipt.json` and `rank0/timings.jsonl` per prompt).
* packet190's record chain WS128: `packet190-record-bundle-k3x/build/device-cards01-p190-a/WS128/run/{summary.json,
  repeat-1/*}`.
* The packet49 oracle results, packet186's two incident64 fixtures (`test_analyze.py`), packet193's device evidence
  (`evidence/diet-B1/window.json`, `samples.jsonl`).
* packet162b's real gate/up rows (`packet162-iq2-lookup/build/micro-inputs/layer{0,24}.bin`, digest-recorded in
  `diet-fixture.json`) and packet103's pinned `p49d_expert_submit.o` objects (`immutable-binaries.json`, re-hashed by the
  build and the kernel-identity gate).

`final_checks.py` re-hashes every file of the analysis map. If packet189/190 ever move or clean these trees, the analysis
gate must be re-run against wherever they are retained. No device row of this packet reads them.

## Ignored and local (`/v5/build/`, `/build/`)

* the compiled engines (`device/`, `gnu-host/`) and the four rebuilt objects per mode;
* the 76 `inherited/` links to the pinned parent objects;
* the CPU fixtures: full-shape, controller mocks, the diet dispatch fixtures (`build/diet-fixture/`), the kernel-identity
  scratch (deleted after the gate), and the k3 state engines with their miniature selections (`build/k3-state/selections/`).

To recreate them: `v5/run_chain.sh p194_v5_build_engine kernel_identity diet_fixture_gate k3_state_gate
p194_v5_full_shape admission_gate analysis_gate controller_gate safety_gate exec_gate loader_gate`, then
`package_rows.py`, `check_queue_rows.py`, `final_checks.py --ready` (each `nice -n 19 taskset -c 8-15,24-31 python3 -B …`).
The build polls `window-*`, `lanequeue-*` and `packet*` units first (an endpoint-restore window is tolerated) and needs the
compilers. The k3 state gate deletes its raw miniature request trees after writing `k3-state.json`.

Disk at preparation: root free 29–30 GB throughout (floor 27 GB); packet 166 MB of which 152 MB hard-linked history; build
tree ~110 MB (cap 2 GB). Nothing was deleted to make room. The device output directories named in the proposal
(`v5/evidence/device-row{0,1}-*-B-p194`) must stay fresh.
