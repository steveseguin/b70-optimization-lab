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

## 3. packet172b: generator failed on the real repo (pin guard); fixed

The tests above passed only in a temporary root. The lanequeue pin guard
resolves its root from its own real path, so the temp-root derive was guarded
against the job-name match `packet58as-*`, i.e. the real packet58as: the
positive test was blind by construction. On the real repo (about 11:00 UTC)
the temporary `lanequeue plan` refused twice:

1. `--packet stage2/packet58as-b-confirm`: the guard globs `ops/<prefix>-*`
   (prefix = text before the first `-`), so `ops/packet58as-orchestration` and
   its pins into packet58as-onecard-spinwait joined the new packet's closure.
   **Fix:** `prefix_gate` refuses any `--packet` whose prefix is not
   `packet<digits><letters>` or matches an existing `stage2/<prefix>-*`,
   `ops/<prefix>-*` or `ops/lane-queue/proposed-p<number>-*`; `--out` must be
   `ops/<prefix>-<label>`. The refusal names the collisions and a free prefix
   (`packet58asa` for that name). It runs before anything is created.
2. `--packet stage2/packet58asb-confirm`: copied metadata still pinned the
   parent (`evidence/argument-gate.json` -> packet58aj `views.json`,
   `views.py`, `window.py`). An audit with `pin_guard.collect_pins` and a
   wrapped `read_metadata` found 303 offending pins in 11 manifests, not one:
   five inherited gates (`argument-gate`, `python-cpu-gates`, `native-parser`,
   `resident-copy-cpu`, `entry-gates`), `k1-cpu.json`, `admission.json`,
   `copy-manifest.json`, `parent-binding.json` (parent lineage, missing in the
   new packet), and `host-admission/measured-peaks.json`/`base-plan.json`
   (100 pins into packet58aj `lineage/owned-inputs`). **Fix:** `relocate_pins`
   rewrites every manifest the guard reads (plus the inherited gates) before
   sealing: a parent pin is repointed to this packet's copy only when that
   copy has the pinned bytes (110 pins); otherwise it becomes
   `{name, parent_relpath, parent_digest}` (193). `host-admission/seal.json`
   is the one re-bound seal (2 entries, siblings this run rewrote; the parent
   binding stays as provenance), because `memory_plan.verify_seal` needs a
   valid bundle seal. Shared immutable pins (packet49 oracle) stay. All
   changes: `evidence/pin-relocation.json` (sealed gate); parent gate digests:
   `build-receipt.json` `inherited_gate_parent_provenance`/`relocated_gates`.
   A final `pin_audit` refuses any pin into the parent or any mutable
   cross-packet pin before the temporary `lanequeue plan` runs the real guard.

Tests (`ops/test_onecard_chain_derive.py`, 10 pass): refusal cases in a
temp root (renamed to free `packet990tmp*` prefixes); prefix-gate cases
(packet58as-b-confirm refusal with a verified free suggestion, CLI refusal
creates nothing, `--out` prefix and name shape); confirmation detection on the
live ledger; and a REAL-layout derive under a random `packet990t*` prefix into
`stage2/` and `ops/`: the guard's `packet_for_job` must pick that packet,
`check_job` passes, no manifest pins the parent, `verify_ready.py` and a
`onecard-chain.sh --check` copy (log path only) pass. A class cleanup
registered before the derive removes both dirs even on failure and asserts
`git status` shows nothing left.

### packet58asb-confirm (derived for real, READY)

Exact command from the brief (no `--cpu-rehearsal`), rc 0, READY last.
Checks: `lanequeue plan` on a temporary queue dir `plan: passed`;
`onecard-chain.sh packet58asb-confirm packet58asb-orchestration --check`
`seal verify: ok`, `check complete`; `verify_ready.py` ready (boot 2cba7160,
the bracket's boot). Chain command digest `bf838b9481d2a30f…`, unit
`packet58-onecard-58as-b`, output `evidence/card0-58as-b`.

This is a confirmation chain, not a resubmission: a second fresh chain of the
packet58as record line (record cmvf31py400furf01tv54rxo7, 34.573 tok/s, chain
a) with the same chain binary `4f957f34ae11011f…` and `--wait-policy spin`.
The generator detects this from the ledger (latest record's packet equals the
bracket packet and its binary matches) and writes it into WINDOW.md and READY
(`confirmation_run`). The copied submission tool still refuses unless fresh
WS128 exceeds 34.57303759192858 tok/s (snapshot) and the live ledger. Not
launched; the chain build binaries stay untracked like packet58as's.

## 4. packet172c: packet58asb launch failure 1 (views.py vs runtime selection); regenerated

The chain-58asb waiter passed `onecard-chain.sh --check`, then unit
`packet58-onecard-58as-b` exited 1 within a second in K1a, before any device
work (GPU fault count unchanged at 2): `window.main -> validate(view) ->
views.py:17 ValueError: sealed overlap runtime selection changed`. The
generator had added `chain_flags` and `wait_policy` to `runtime-selection.json`
but left the inherited `views.py` literal unchanged. packet58as (hand-built)
had added `wait_policy='spin'` to both. None of seal/verify_ready/lanequeue
plan/`--check` runs a window's Python entry, so none could see it.

- **Fix:** `bind_views` generates both from one source,
  `selection_extra(flags)`: `views.py` gets
  `if runtime!=dict(**GENERATED_RUNTIME_SELECTION, <parent literal>)` (exactly
  one such check, no key clash with the parent selection, else refused) and
  `runtime-selection.json` is the parent selection plus the same dict.
- **New acceptance step:** `predevice_gate` (also
  `onecard_chain_derive.py --predevice-check <packet>`) runs every chain
  window's real `window.main` with the queue_runner `--plan` argv and the
  recorded oneAPI library path, up to its first device-evidence boundary
  (K1a/K1b: output creation; KD..WS128: previous-window prerequisite). Real:
  argparse, `validate(view)`, authorization flag, `closed_environment`,
  `build_gate`, `window_plan`, storage, fault-review parsing, fault latch,
  record construction. Simulated: priority, affinity, user-unit cgroup. It
  refused the failed packet58asb-confirm on all 7 windows with the launch
  error and passes on the packet58as packet that ran chain a. The generator
  runs it before the temporary lanequeue plan; READY records it
  (`predevice_rehearsal`) and `ops/packet58asb-orchestration/predevice-rehearsal.json`.
- **Tests:** 11 pass. New: the real-layout derive passes the rehearsal, and a
  transient copy of the failure mode (views literal reverted and re-sealed)
  must refuse on every window with the launch error; both files are restored
  and the seal digest is checked again.
- **Failed launch evidence** (`K1a.log`, `queue.json`, fault review and its
  kernel journal, superseded READY): `data/2026-10-19-packet58asb-failed-launch-1/`
  with `SHA256SUMS.txt`. The derived packet and orchestration were then removed
  and regenerated fresh under the same names with the exact brief command.
- **Regenerated packet58asb-confirm:** rc 0, READY last; temporary lanequeue
  plan passed; `--check` seal verify ok / check complete; `verify_ready` ready;
  `--predevice-check` passed on all 7 windows; pin audit 0 parent pins. Chain
  command and digest `bf838b9481d2a30f…` unchanged (the fix is inside the
  packet). Still a confirmation chain, not a resubmission. Not launched.

## 5. packet172d: packet58asb launch 2 stopped after the KD native run; regenerated

K1a, K1b and the KD native receipt passed (GPU fault count unchanged at 2).
KD's Python post-processing then stopped: `window.json` stop_reasons
`[Errno 2] ... packet58asb-confirm/lineage/fixtures/58c-supervisor/source-manifest.json`
(`window.postload_observation -> legacy_memory_plan.seed_observation`), and
lane admission did not complete. The generator never copied the parent's
`lineage/`; none of the CPU checks executes post-native code. Same class as
packet58ame this morning.

- **Fix:** `lineage/` and `screen-reader/` join the copied dirs (byte for byte,
  sealed as sources). With lineage present, 30 more parent pins are repointed
  to identical copies instead of provenance (275 relocations in total).
- **Static closure check** (`closure_check`, `--closure-check`): AST scan of
  every non-test harness module for constant joins under `Path(__file__)`
  roots (and names derived from them) plus `lineage/`/`fixtures/` literals.
  Anything the parent has must exist in the derived packet. On the failed
  packet it refused with the 58c-supervisor fixture, `lineage/58ag-build-commands.json`,
  `lineage/synthetic-lookup-receipt.json` and `screen-reader/drain_gate.py`.
- **Post-native rehearsal** (`postnative_gate`, `--postnative-check`): the
  window's post-native code on a temp copy of packet58as chain-a's real device
  evidence (`stage2/packet58as-onecard-spinwait/evidence/card0-58as-a/<window>`),
  using that chain's own budgets and memory records. On the failed packet:
  KD..WS128 FileNotFoundError on the fixture (the launch error), K1a/K1b pass.
- **Tests:** 12 pass. New: the regenerated packet passes both checks; with the
  fixture moved aside, both refuse with the launch-2 error, then it is restored.
- **Failed launch 2 evidence:** `data/2026-10-19-packet58asb-failed-launch-2/`
  (`card0-58as-b/` K1a/K1b/KD receipts and logs, queue.json, fault review,
  superseded READY; `SHA256SUMS.txt` covers 498 files). The per-window
  `native-home/` Level Zero compiler caches (15 MB) moved out of Git to
  `/home/steve/own-xpu-runtime-results/packet58asb-confirm/failed-launch-2/`;
  their checksums stay in `SHA256SUMS.txt`. `*.jsonl` files (window
  journals, host-memory samples) are gitignored under `data/` and stay on
  disk there, also covered by `SHA256SUMS.txt`.
- **Regenerated packet58asb-confirm** (exact brief command, fresh dirs): rc 0,
  READY last; lanequeue plan passed; `--check` ok; `verify_ready` ready;
  `--predevice-check`, `--closure-check` (84 targets) and `--postnative-check`
  (7 windows on card0-58as-a) passed; pin audit 0 parent pins. Chain digest
  `bf838b9481d2a30f…` unchanged. Confirmation run, not a resubmission. Not
  launched.
