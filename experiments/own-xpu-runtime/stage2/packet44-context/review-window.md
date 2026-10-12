# Independent CPU review of coordinator wrappers

No native binary or device ran. `context-window-gates.json` records 10 Python
mock tests. The main-path matrix contains 22 cases: K0, K1a, K1b, K2, W0p, KD,
W2m, WS and WSs at both capacities, with both 64-token and 128-token manifests
for WS/WSs. Cases execute the real `window.main` through post-run receipt
serialization; external/device actions and source seals are mocked. K2 executes
its summary orchestration and writes both rank dispatch aliases. Additional
tests inject a full-disk exception during that summary and a compression failure
after the successful summary. The former fails without a boot latch; the latter
preserves the pass and raw evidence.

The direct fixture-launch matrix covers eight combinations (K0/K1a/K1b/K2 ×
two capacities), checking context flags and unchanged child environment. Direct
KD mocks run two distinct fresh owner PIDs at each capacity, complete fixture
comparison and summary receipts, and inject post-run compression failures. Raw
logs and retention diagnostics remain available. These tests validate
orchestration, not the bytes produced by an actual device.

`window-mocked-inherited-tests.json` records 36 inherited non-binary tests.
The inherited `test_class_diagnostic_contract` is deliberately excluded here
because it executes the host binary; it belongs to the separate CPU runtime
gates. No fixture/CPU gate result is fabricated by this mocked wrapper test.

## Findings fixed

- K1 chooses the sealed host fixture hash for its requested context.
- KD chooses `capture-run-incident-retrospective-c{context}.json` and the matching
  `draft_capture_fixture_sha256_by_context` entry, so caches at different
  allocation capacities are never compared against the wrong capture.
- Both fixture and KD commands forward `--context`; the pipeline already
  forwards it to both target ranks and their memory admission.
- With only `LD_LIBRARY_PATH` supplied, native OMP threads default to two. The
  path value is forwarded byte-for-byte, including empty components and spaces.
  W windows continue to require a nice-0 parent. Affinity is neither replaced nor
  widened, so a coordinator may apply `taskset` externally.
- A rank nonzero exit or unexpected native channel EOF raises a structured owner
  failure carrying the rank output directory. It latches only with the explicit
  `device-contact.json` marker. Storage failure evidence, wrapper errors and
  coordinator cancellation do not latch. New kernel fault lines remain a latch
  reason, including faults discovered while recording another error. Historical
  lines before the wrapper cursor are recorded but never replayed as new faults.
- KD and general post-run compression failures keep raw files and preserve the
  window's completed verdict. A just-exited process with no RssAnon line is
  tolerated. JSON receipts carry strings, integers and collections, not Paths.
- Storage mock checks verify the 6,000,000,000-byte wrapper build ceiling and
  8,000,000,000-byte root free-space floor. The agent's own work remains subject
  to the separately tighter 4 GB build rule.

## Build receipt contract

`window.py` reads these mandatory top-level fields:
`passed`, `sources`, `official_manifest_sha256`, `memory_plan`,
`artifacts_sha256`, `p33_linked_fixture_host_sha256`,
`nongemv_fixture_host_sha256_by_context`, and `input_sha256`.
The context fixture map needs string keys `256`, `4096`, `32768`.

KD additionally reads `draft_capture_fixture_sha256_by_context` with those
three context keys and `draft_capture_input_sha256['incident-retrospective']`.
`artifacts_sha256` must contain `gnu-host/own-rt-iq3`, `device/own-rt-iq3`,
`device/jit-smoke`, `device/nongemv-fixtures`, `device/p33-linked-fixtures` and
`device/k2-fixtures`. All other artifact entries are also verified.

Optional KD carry-forward proof `model_gate_carry_forward`, if present, must
contain `passed`, `path`, `sha256`, and `model_binary_mapping`; its verified file
must map `gnu-host` to `current_sha256` and `executed_sha256`. Omit the optional
proof when this packet's own freshly executed binary is the reference.

The legacy standalone `fixture_support.py` entry also reads `cpu_tests_sha256`,
`census_sha256`, `nongemv_fixture_host_sha256` and the
`artifacts_sha256['host/own-rt-iq3']` compatibility alias. Preserve these keys
only with real matching evidence if that entry remains callable. Its old flat
fixture hash cannot substitute for the new context-specific wrapper selection.

Device execution, real K2 duration, actual memory residency, and native kernel
fault behavior remain coordinator-window checks. Mock passes cannot satisfy
those gates.
