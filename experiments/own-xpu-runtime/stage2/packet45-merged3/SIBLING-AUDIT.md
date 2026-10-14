# Packet45 sequential-owner sibling audit

CPU-only audit of the current coordinator, imported gates, registered seal gates,
and inherited fixture/window helpers. The device inputs are the owner's existing
K1a receipts on both pairs, read as JSON only. No device binary was run.

| Constant or structural assumption checked | Source of comparison | Verdict |
|---|---|---|
| K1 four sequential owners | `fixture_driver.cpp` teardown assembly and allocation namespaces; both device receipts | Stale. Replaced by exact ordered namespaces: fixture, actual-adapter, small-gemv, gemv-k2, p39-fixture. Require complete status, exit 0, safe exit, integer zero live bytes/in-flight, exactly one card, no missing/extra/duplicate/mixed owners. |
| Legacy K2 four-owner call in `fixture_support.py` | Same driver, with `PACKET26_K2` | Stale. Uses the same named-owner validator now. The standalone legacy entry remains disabled. |
| Current `window.py` K2 post-run checks | Shared K1/K2 driver | Incomplete: timing summary alone did not check teardown. Added the full named-owner gate before timing aggregation. |
| `validation_gate.py`: `93+66` source fixtures | Driver adds four QSA operators at each registered length | Stale. Uses `93 + 4*len(LENGTHS[context])`; 117 at 256/4096, 121 at 32768. |
| Validate-only K2 expected every timing class | `p39_fixture.cpp`: timing loop requires `timing && !fixture_validation::only` | Stale for merged CPU validation. Exactly the eight p39 timing classes are absent; require all 56 scenario pairs and every other registered class. Device timing still requires all 65 classes. |
| CPU rehearsal accepting any failed K2 speed summary | Real host K2 events and the merged registry | Gap closed. A separate structural check requires 57 CPU event classes, registered candidates/workloads, both variants, full stage counts and zero timestamps. Missing rows cannot hide behind the expected timing failure. No synthetic timestamps or performance pass. |
| Inherited `full_wrapper_gate.py`: context256, dispatch-p38, old scalar capture/seal keys, handwritten window sequence | Current coordinator arguments and `window.main` capacity/draft fields | Stale unused harness. Replaced with the maintained exact coordinator rehearsal entry. |
| K0 two children / two cards | `run_fixtures` JIT jobs | Correct: two simultaneous `jit-smoke` processes in device mode; explicitly labeled structural shim on CPU. |
| K1a/K1b two child binaries and four distinct PIDs across repeats | `run_fixtures`, `fresh_k1_owners` | Correct: `nongemv-fixtures` then `p33-linked-fixtures`, sequential on one card; two new processes per window. Five teardown rows belong to the first child, not five child processes. |
| K2 one child binary | `run_fixtures` and CMake target | Correct: `k2-fixtures`; it owns the same five sequential teardown rows. |
| KD two fresh owners / one teardown per owner | `draft_window.py` and runtime capture mode | Correct: one selected-dispatch host reference, then two fresh owners on `card + draft_rank`; every capture/state byte compared. |
| W0p / W2 / WS / WSs binary set and rank count | `window.py`, `pipeline.py`, `suite.py` | Correct: two `own-rt-iq3` ranks. Native controller is linked, not an extra device binary. WSs is sequential decoding within the two-rank runtime. |
| p33 18 families, 36 splits, 6 modes, 216 checks, 1512 output rows, 1024-byte argument limit | `p33_linked_fixture.cpp` and actual CPU outputs | Correct and unchanged. Two compiler receipts give 432 checks; the linked program is a separate K1 child. |
| K1 fixture floor 72, edge counters 20/1/1 | Original fixture list plus driver additions | 72 is a minimum base-fixture floor, not an expected total. No 170-fixture equality remains in the active gate. Exact per-context host output digests and the seal's formula qualify the complete merged fixture set. |
| K1 exact totals and component counts | `capacity_fixture_gate.py`, `seal45.fixture_bindings`, actual driver | Correct: 218 checks at 256/4096, 230 at 32768; 55 adapter + 220 small GEMV + 3096 GEMV + 56 p39 = 3427 additional checks. |
| K2 check totals | Same source-bound formula | Correct: `24 + 20*len(lengths)` = 144/144/164; source fixture totals are `72 + 4*len(lengths)` = 96/96/100. |
| Capacity grid and QSA budget | Driver, `capacity_fixture_gate.LENGTHS`, `k2_summary.CONTEXT_LENGTHS` | Correct: 256/4096/32768 capacities, six/six/seven lengths, four QSA operator classes, fixed 2048 selection budget. |
| K2 timing constants | Driver and `k2_summary` | Correct: 200 device repetitions, 8-way heavy-weight rotation, full stage coverage and four-second submission bound. CPU validation has one repetition and zero timestamps. |
| K2 watchdog 14400 seconds | Current duration plan | Sufficient: minimum 2008/2288/11536 seconds for the three capacities. Estimates remain estimates. |
| 48 model layers, 20480-byte real layer fixtures, 8-token subset, 384 layer outputs | Official lane geometry and real oracle | Correct: rank placement changes to 22/26 or 24/24, total remains 48. Miniatures have separate geometry. |
| Suite caps / request count | Bound suite manifest and current `window.py` | Correct: 32/64/128 from manifest; storage uses warmup plus prompt-count times repeat, not a fixed twelve requests. CPU chains use two miniature prompts at cap128. |
| Draft capture 6 arms, 63 reference files, 68 total state/fixture files | `capacity_draft_gate.py`, `seal45.draft_bindings` | Correct: two host compilers times three capacities; placement is additionally covered by six real cases and three same-capacity pairs. |
| Four rows in inherited `fixture_gate.py` | Two compilers times two fresh fixture processes | Correct: a repeat matrix, not an owner count. The active capacity gate additionally covers all three capacities. |
| 34 GEMV validation workloads / four or six mode sets | `gemv_timing.cpp` and actual fresh GNU/Intel entry traces | Correct; the audited `validation_gate.py` passed both compilers including poison and continuation controls. |
| Controller 1123 cases / mailbox 5 gates / 24 long random patterns | Native test constructors and normal/ASAN/TSAN output | Correct: 3369 controller cases and 15 mailbox gates across three builds. |
| Miniature 79 cases / real 6 cases / three placement pairs / 17 semantic buffers | Registered campaign matrices and `real_cross_placement_gate.py` | Correct: capacity and placement are explicit dimensions; no packet44-only rank1 assumption. |
| Wrapper 101 tests / 78 mocked combinations | `wrapper_cpu_gate.py` test enumeration | Expanded to 115 tests plus 27 actual coordinator windows. The 78 mocks remain supplemental; their old zero-child field is now explicitly named `mock_rank_processes_started`. |
| Seal 24 gate receipts / 41 build artifacts | `seal45.GATES`, four mode-build receipts | Correct. New full-chain proof is required inside both existing wrapper receipts, keeping 24 top-level gates. All artifacts are rehashed. |
| Older `packet26`/`packet37`/`packet38` schema names | Actual emitted C++ receipts and archive framing | Intentional wire-format identities, not binary/path selection. Do not rename them as part of a host gate fix. |
| Legacy `fixture_support` CONFIG, standalone `cpu_gate` and old seal mains | Import/call-site search; disabled `fixture_support.__main__`; `build.py seal` imports `seal45` | Historical helpers are not the packet45 coordinator/admission path. Current build uses gnu-host/icpx-host/asan/device and context-keyed receipts. No active path uses the old `host/own-rt-iq3` lookup or legacy 256-only CONFIG. |

The original 78 mocked window combinations replaced both `run_fixtures` and
`fixture_receipt_gate`, and mocked prerequisite receipts. The separate sealed
admission test deliberately stopped at blocked launchers. Neither could observe
the actual five-owner receipt. The required wrapper suite now executes the actual
`coordinator_windows.sh` for both ranks at 4096 and rank0 at 32768, with real host
children, receipt gates, dependency checks, summary generation and retention.
The new owner and K2 structural mutation tests reject omissions and same-count
substitutions. The seal binds the rehearsal sources, host binary, matrix and
verified retained archive; a mocked-window-only report can no longer seal.
