# 2026-10-19 packet172 (ops): one-card chain generator + GPU-time accounting fix

CPU-only ops work. No GPU, service, queue, packet-tree or orchestration-dir change.
Codex started it and hit its usage limit; Claude finished it.

## Why

After the packet58as v5 win the host idled about 50 minutes while the chain
orchestration was derived by hand twice: packet58asc, then packet58asd because
the spin wait could be chosen only through the bracket table. The chain windows
cannot use that table.

## 1. `ops/onecard_chain_derive.py`

Usage and gates: `experiments/own-xpu-runtime/ops/README.md`, section
"One-card chain generator". In short: bracket gate, `--help` gate (device
binary in `entry_sandbox`, host build plain), copy of the parent chain harness
with the flags added to every model window, real-parser gate
(`--p58r-parse-test`) per model window, seal, `verify_ready`, temporary
`lanequeue plan`, READY last. Any refusal exits 2, removes the directories that
run created and writes no READY.

Refusal cases covered by `ops/test_onecard_chain_derive.py` (all pass):

- failed bracket (`candidate_beats_all_controls` false);
- bracket-table-only dimension: the packet58aj binaries lack `--wait-policy`
  (the device binary has no `--help` at all) while packet58as names
  `wait_policy` in `native/bracket_table.hpp`/`views.py`/`runtime-selection.json`;
  the refusal names the packet58asc failure and the packet58asd fix;
- a flag missing from `--help` (`--no-such-option`).

The parser gate also refuses when a window argv lacks the flag, when the parser
rejects the chain argv, when an invalid value is accepted (acceptance would prove
nothing), and when the argv without the flag no longer parses.

Positive test: packet58aj-orchestration plus the packet58asd chain binaries and
the packet58as v5 summary go to `packet58as-derived` in a temporary repo root.
Existing entries there are read-only symlinks; `suite-inputs-20261012` is a
real copy, because the harness requires its input bundle to resolve inside the
root. A temporary copy of `fn-run/onecard-chain.sh` then runs with only `cd`
and the log path changed: `seal verify: ok`, `check complete`, with
unit/output/fault-review derived from READY.

### Differences from the hand-built packet58as-orchestration

- **Model-window argv:** KD/W2m/WS/WS128x/WS128 are identical to packet58asd's
  `wait-policy.json` argv (packet name aside). The only difference is
  `--wait-policy spin`: the generator appends it at the end (argv index 64),
  while the hand-built argv put it before `--lookups` (index 42). The native
  parser does not depend on order; the parser gate proves this on the real
  argv.
- **Packet:** the generator writes a new chain packet (`--packet` must not
  exist). The hand-built version edited the bracket packet in place
  (`packet58as-onecard-spinwait`). So the chain command differs only by packet
  path, and therefore its digest differs.
- **Harness source:** the generated packet copies the parent (packet58aj)
  harness and adds a generated flag block to `suite_driver.py` and
  `composition.py`. The hand-built version used the bracket packet's own
  modules with hand edits (`views.py`, `screen_gate.py`, `verify_ready.py`,
  `packet58_submission.py` and others). It also has bracket-only and
  rebuild-only scripts (`wait_policy_gate.py`, `rebuild_wait_policy.py`,
  `flags_gate.py`, `analyzer_gate.py`, `cpu_gate.py`, `finalize.py`), which a
  chain does not need.
- **`seal.py` / `verify_ready.py`** are generated, because the parent's are
  packet specific. `verify_ready.verify()` still calls the parent harness's
  `window.build_gate()` (sources, artifacts, CPU gates, oracle binding), checks
  the submission pins and the fresh output, re-hashes the bracket summary and
  `window.json`, and requires the bracket boot to equal the current boot. The
  test passes `--cpu-rehearsal`, which READY discloses as `bracket_boot_check`.
- **Gates:** the parent's CPU gate receipts are copied byte for byte and
  re-bound by the seal. `evidence/chain-flags.json` replaces packet58asd's
  `wait-policy.json`, `chain-native-interface.json` and `native-parser.json`.
  Not reproduced: the GNU/Intel miniature byte-equality run, the conflict and
  draft-capture refusals, the submission rehearsal and the 137-test Python
  suite. These were packet58asd-specific gates on the rebuild itself. A new
  native change still needs its own rebuild gate before derivation.
- **Plan output:** packet58aj's `queue_runner.py --plan` prints text, and the
  current lanequeue refuses that. The generator applies packet58asc's exact
  JSON plan line, only on an exact match, and records this as `plan_output` in
  `derived-chain.json`.
- **READY fields:** the generated READY adds `chain_flags`, `generator`,
  `parent_chain_binary_sha256`, `parent_provenance` and `bracket_boot_check`.
  It omits the rebuild-specific `bracket_binary_sha256`,
  `chain_interface_patch_sha256`, `native_identity`, `python_tests`,
  `wait_policy_gate_passed` and `submission_rehearsal_passed`. Provenance
  entries are only `{name, parent_relpath, parent_digest}` records.
- **Same values:** windows, gaps, wait seconds, bracket rates, drift, minimum
  gain, pinned predecessor and chain binary sha256.

## 2. `gpu_time_review.py`

A successful lanequeue START/DONE pair (rc 0, Result success, no admission
cause) now counts as device occupancy when a standalone micro left no child
clock. It is labelled `lanequeue START/DONE device evidence (no child clock)`.
This covers packet166 B1, lane B, 08:25:15 to 08:28:59 UTC, 223.96 s (result
387a97e4f). Refusals, failures, open STARTs and known admission waits do not
count. The test uses the real interval (24 tests pass). Commit 737330c3a.
