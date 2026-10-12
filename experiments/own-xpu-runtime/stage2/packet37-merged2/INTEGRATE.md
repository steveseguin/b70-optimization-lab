# Packet36 and packet37 integration

Base: packet32-pipeline, commit `2e8ec7585c`. Packet36 and packet37 must be
merged onto that common base; no other packet is a runtime base. The inventory
below compares actual local bytes, and `integrate-files.json` stores hashes.
Regenerate after the final edit with
`nice -n 19 ionice -c 3 python -B integration_inventory.py` from this directory.
Build scratch and copied historical receipts are excluded from source merge
work. Historical receipts moved under `inherited-packet32/` retain their own
identity and are not packet37 evidence.

Packet36 contributes its draft provider on rank1. Preserve packet37's owner,
backend and prepared command layer when merging. The primary intersecting
files are `main.cpp`, `rank.hpp`, `pipeline.py`, `CMakeLists.txt`, `window.py`,
the CPU gates, and receipt schemas. Merge the draft-provider calls into the
existing rank1 protocol boundary, not into captured target launch objects.
Any provider scratch allocation or upload must finish before target replay;
never replace a captured target pointer or free its owner while a command can
still use it. Both parity launch sets belong to the target's transaction.
Draft proposals cannot advance the committed position, append to target KV,
or choose rollback state; target verification and packet32 commit/rollback
rules remain authoritative. The draft must release its own resources without
altering rank0's lookup residency. Preserve unchanged target arithmetic and
uncompressed cache throughout the merge.

Keep packet37's two complete prepared binding sets when draft guesses are
wrong. Select the set for the current alternate-buffer parity at each half,
then preserve packet32's rollback/swap decision. Regenerate plans only at a
quiescent boundary if an allocation identity or graph changes. Rerun the
argument-block comparisons in all modes, forced-miss and rollback-state
gates, both fresh K1 owners, the real-model oracle modes, and provider-specific
identity gates after the merge. K2 timing from this packet does not certify a
later draft merge's speed or quality.

A native controller is a separate implementation, not included here. It needs
the same two rank-owner lifetimes, bounded IPC protocol, stop propagation,
transaction IDs, guess requests, target verification, parity-aware half-run
ordering, rollback acknowledgement, error/fault handling and final resource
release. It must forward affinity and coordinator library paths, retain the
host and pipeline receipts, and expose diagnostic all-hit/all-miss injections.
Move scheduling and receipt collection out of Python without moving target
arithmetic or accepting unverified draft tokens. Prove the native controller
against the current mini and real-model token/layer/state oracles before any
performance comparison. A controller speedup remains unmeasured here.

## File-by-file changes

| File | Change | Reason |
| --- | --- | --- |
| `ARTIFACTS.md` | added | Document packet37 behavior, coordinator commands, pending device gates and merge/lifetime rules. |
| `BINARY-HASHES.md` | changed | Document packet37 behavior, coordinator commands, pending device gates and merge/lifetime rules. |
| `CLOSEOUT.md` | changed | Document packet37 behavior, coordinator commands, pending device gates and merge/lifetime rules. |
| `CMakeLists.txt` | changed | Link prepared-host and packet33 translation units with strict compile/link precision flags. |
| `DEADLINES.md` | changed | Document packet37 behavior, coordinator commands, pending device gates and merge/lifetime rules. |
| `DO-NOT-REPEAT.md` | changed | Document packet37 behavior, coordinator commands, pending device gates and merge/lifetime rules. |
| `KERNELS.md` | added | Document packet37 behavior, coordinator commands, pending device gates and merge/lifetime rules. |
| `LIFETIME.md` | changed | Document packet37 behavior, coordinator commands, pending device gates and merge/lifetime rules. |
| `README.md` | changed | Document packet37 behavior, coordinator commands, pending device gates and merge/lifetime rules. |
| `ROLLBACK.md` | changed | Document packet37 behavior, coordinator commands, pending device gates and merge/lifetime rules. |
| `WINDOW.md` | changed | Document packet37 behavior, coordinator commands, pending device gates and merge/lifetime rules. |
| `adapter.cpp` | changed | Prepare the selected packet33 QSA dispatch path with unchanged non-GEMV bindings. |
| `adapter_fixture.cpp` | changed | Use measured packet29 non-GEMV incumbents in K2. |
| `argument-block-tests.json` | added | Record or execute focused CPU validation and independent review. |
| `argument-state-gates.json` | added | Record or execute focused CPU validation and independent review. |
| `argument-state-registry.json` | added | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `argument_block.hpp` | added | Guard pointer-only bounded launch blocks for prepared submissions. |
| `argument_block_test.cpp` | added | Record or execute focused CPU validation and independent review. |
| `argument_state_gate.py` | added | Record or execute focused CPU validation and independent review. |
| `audit_rollback.py` | changed | Connect inherited CPU validation/build harnesses to packet37 additions. |
| `backend.hpp` | changed | Add capture/replay support and prepared command representation. |
| `build-receipt.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `build.py` | changed | Connect inherited CPU validation/build harnesses to packet37 additions. |
| `canary-host-gates.json` | changed | Record or execute focused CPU validation and independent review. |
| `cleanup.py` | changed | Connect inherited CPU validation/build harnesses to packet37 additions. |
| `cpu-tests.json` | changed | Record or execute focused CPU validation and independent review. |
| `dispatch-incumbent.json` | added | Copy the measured packet29 map solely as K2 incumbent provenance. |
| `dispatch-p33.json` | added | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `dispatch.hpp` | changed | Admit packet33 QSA implementation identifier 3. |
| `dispatch_registry.hpp` | changed | Extend the closed C++ dispatch vocabulary with five packet33 kernels. |
| `entry-codes.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `evidence/fixture-gates-full.json.gz` | changed | Retain packet-local implementation or validation support required by the merged runtime. |
| `evidence/preparation-logs-p37-6e8738e7636297b1.json.gz` | added | Retain packet-local implementation or validation support required by the merged runtime. |
| `evidence/real-hit-rank0-arguments.jsonl.gz` | added | Retain packet-local implementation or validation support required by the merged runtime. |
| `evidence/real-hit-rank1-arguments.jsonl.gz` | added | Retain packet-local implementation or validation support required by the merged runtime. |
| `evidence/real-miss-rank0-arguments.jsonl.gz` | added | Retain packet-local implementation or validation support required by the merged runtime. |
| `evidence/real-miss-rank1-arguments.jsonl.gz` | added | Retain packet-local implementation or validation support required by the merged runtime. |
| `evidence/real-ngram-rank0-arguments.jsonl.gz` | added | Retain packet-local implementation or validation support required by the merged runtime. |
| `evidence/real-ngram-rank1-arguments.jsonl.gz` | added | Retain packet-local implementation or validation support required by the merged runtime. |
| `evidence/real-none-rank0-arguments.jsonl.gz` | added | Retain packet-local implementation or validation support required by the merged runtime. |
| `evidence/real-none-rank1-arguments.jsonl.gz` | added | Retain packet-local implementation or validation support required by the merged runtime. |
| `fixture-gates.json` | changed | Record or execute focused CPU validation and independent review. |
| `fixture_driver.cpp` | changed | Gate linked packet33 QSA under K1 and time it under K2. |
| `gates.py` | changed | Connect inherited CPU validation/build harnesses to packet37 additions. |
| `gemv_timing.cpp` | changed | Gate/time packet33 GEMVs and same-run packet29 controls, retaining R5 alternatives. |
| `integration_inventory.py` | added | Regenerate this explicit file-by-file merge inventory. |
| `k2-admission-tests.json` | added | Record or execute focused CPU validation and independent review. |
| `k2-class-registry.json` | changed | Declare complete candidates, workloads and packet29 incumbent identities. |
| `k2-selection-tests.json` | added | Record or execute focused CPU validation and independent review. |
| `k2_incumbents.hpp` | added | Compile the registered packet29 controls into native fixtures. |
| `k2_summary.py` | changed | Port measured fusion selection; compare both HC sites and emit rank dispatch maps. |
| `kernel-registry.json` | changed | Extend the machine-readable closed kernel vocabulary. |
| `kernel-sizes.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `kernel-submissions.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `kernel_gate.py` | changed | Record or execute focused CPU validation and independent review. |
| `main.cpp` | changed | Prepare/replay both rank parities, residency and per-token host receipts. |
| `math_gate.py` | changed | Record or execute focused CPU validation and independent review. |
| `mini-asan.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `mini-gnu-host.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `mini-icpx-host.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `oversized-capture.log` | changed | Retain packet-local implementation or validation support required by the merged runtime. |
| `owner-gates.json` | changed | Record or execute focused CPU validation and independent review. |
| `owner.cpp` | changed | Capture stable launches, preserve lifetime rules, and remove redundant dependencies. |
| `owner.hpp` | changed | Own prepared command state and validated allocation/event lifetimes. |
| `owner_api.hpp` | added | Expose prepared backend operations through the owner API. |
| `p33-candidate-gates.json` | added | Extend and gate existing packet33 arithmetic, shape specialization or binding entry points. |
| `p33-linked-fixture-gates.json` | added | Extend and gate existing packet33 arithmetic, shape specialization or binding entry points. |
| `p33_candidate_cpu.cpp` | added | Extend and gate existing packet33 arithmetic, shape specialization or binding entry points. |
| `p33_candidate_gates.py` | added | Extend and gate existing packet33 arithmetic, shape specialization or binding entry points. |
| `p33_candidates.hpp` | added | Extend and gate existing packet33 arithmetic, shape specialization or binding entry points. |
| `p33_linked_fixture.cpp` | added | Extend and gate existing packet33 arithmetic, shape specialization or binding entry points. |
| `p33_linked_fixture_gate.py` | added | Extend and gate existing packet33 arithmetic, shape specialization or binding entry points. |
| `p33_submit.cpp` | added | Extend and gate existing packet33 arithmetic, shape specialization or binding entry points. |
| `p33_submit.hpp` | added | Extend and gate existing packet33 arithmetic, shape specialization or binding entry points. |
| `p33r2.cpp` | added | Extend and gate existing packet33 arithmetic, shape specialization or binding entry points. |
| `p33r2.hpp` | added | Extend and gate existing packet33 arithmetic, shape specialization or binding entry points. |
| `pipeline.py` | changed | Carry packet37 rank preparation and per-token receipts through the Python controller. |
| `prepared-host-benchmark.json` | added | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `prepared-invalidation.json` | added | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `prepared_host_benchmark.py` | added | Qualify prepared launch equivalence, allocation-free replay or lookup residency. |
| `prepared_invalidation_test.cpp` | added | Qualify prepared launch equivalence, allocation-free replay or lookup residency. |
| `prepared_issue_benchmark.cpp` | added | Qualify prepared launch equivalence, allocation-free replay or lookup residency. |
| `prepared_submission.hpp` | added | Qualify prepared launch equivalence, allocation-free replay or lookup residency. |
| `prepared_unit_gate.py` | added | Qualify prepared launch equivalence, allocation-free replay or lookup residency. |
| `rank.hpp` | changed | Bind prepared submissions to speculation parity and rollback transaction state. |
| `real-campaign-icpx-host.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `real-campaign.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `real-hit.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `real-icpx-host-hit.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `real-icpx-host-miss.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `real-icpx-host-ngram.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `real-icpx-host-none.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `real-miss.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `real-ngram.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `real-none.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `real_campaign.py` | changed | Run inherited real-model oracle modes through packet37 binaries. |
| `resident-host-gates.json` | changed | Record or execute focused CPU validation and independent review. |
| `resident_host_gate.py` | changed | Qualify prepared launch equivalence, allocation-free replay or lookup residency. |
| `review-controller-tests.json` | changed | Record or execute focused CPU validation and independent review. |
| `review-dense-independent.json` | added | Record or execute focused CPU validation and independent review. |
| `review-dense-independent.md` | added | Record or execute focused CPU validation and independent review. |
| `review-identity-sources.json` | changed | Record or execute focused CPU validation and independent review. |
| `review-k2-port.md` | added | Record or execute focused CPU validation and independent review. |
| `review-k2-selection.json` | added | Record or execute focused CPU validation and independent review. |
| `review-k2-selection.md` | added | Record or execute focused CPU validation and independent review. |
| `review-linked-fixture.json` | added | Record or execute focused CPU validation and independent review. |
| `review-linked-fixture.md` | added | Record or execute focused CPU validation and independent review. |
| `review-native-faults.json` | changed | Record or execute focused CPU validation and independent review. |
| `review-prepared-gates.json` | added | Record or execute focused CPU validation and independent review. |
| `review-prepared.md` | added | Record or execute focused CPU validation and independent review. |
| `review_prepared_gate.py` | added | Record or execute focused CPU validation and independent review. |
| `rollback-inventory.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `scratch-cleanup.json` | changed | Record packet37 build, gate or kernel receipts; never reinterpret inherited evidence as a new run. |
| `single_device.cpp` | added | Replay prepared device operations without per-launch discovery or binding work. |
| `source-packet32.json` | added | Record the source packet identity; copied historical receipts remain inherited evidence. |
| `submission-overlay-gates.json` | added | Record or execute focused CPU validation and independent review. |
| `submission_overlay.py` | added | Maintain the precision/dependency overlay used by the build. |
| `test_k2_admission.py` | added | Record or execute focused CPU validation and independent review. |
| `test_k2_selection.py` | added | Record or execute focused CPU validation and independent review. |
| `test_submission_overlay.py` | added | Record or execute focused CPU validation and independent review. |
| `test_window.py` | changed | Record or execute focused CPU validation and independent review. |
| `validation-gates.json` | changed | Record or execute focused CPU validation and independent review. |
| `validation_gate.py` | changed | Record or execute focused CPU validation and independent review. |
| `validation_mirror.py` | changed | Mirror new registry entries in CPU validation contracts. |
| `window-tests.json` | changed | Record or execute focused CPU validation and independent review. |
| `window.py` | changed | Prepare packet37 windows, provenance binding, deadlines and fault-safe ownership. |
| `wrapper-contract-tests.json` | added | Record or execute focused CPU validation and independent review. |
| `INTEGRATE.md` | added | Human-readable merge instructions and generated inventory. |
| `integrate-files.json` | added | Machine-readable hashes and reasons for every changed source/evidence file. |
