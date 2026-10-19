# CPU entry and report rehearsal

`rehearse_entry.py PROPOSAL --report --json` checks native entry packaging and
runs the real report on invented inputs. It never admits a device job. Report
children have a 45-second timeout, 2 GiB address-space limit, nice 19, CPUs
8–15/24–31, and closed stdin. Their audit guard rejects subprocesses, devices,
model/data reads and writes outside the temporary output tree. A caught guard
violation still fails the rehearsal. These are trusted repository Python
sources, not a sandbox for hostile code. Synthetic reports prove report routing
and schema handling only; they are not quality, speed or readiness evidence.

Run from the repository root:

```sh
nice -n 19 taskset -c 8-15,24-31 bash -c '
  ulimit -v 2097152
  python3 -B experiments/own-xpu-runtime/ops/rehearse_entry.py \
    experiments/own-xpu-runtime/ops/lane-queue/proposed-p58aq-split-A.txt \
    --report --json
' </dev/null
```

## Standalone micro contracts

A `run_micro.py` entry, or an entry with
`plan.entry_rehearsal.kind = "micro"`, provides `parser()` with a `--lane`
argument and `report_completed(output: Path)`. The latter must call the actual
declared analyzer and return the JSON object it publishes. No device entry or
admission is called. Put `report-contract.json` beside the entry, or name a
packet-relative JSON file in `plan.entry_rehearsal.report_contract`.

Example for a new schema:

```json
{
  "schema": "own-runtime.report-contract.v1",
  "analyzer": "micro_analyze:evaluate",
  "fixture_generator": "report_fixture:generate",
  "samples": {
    "path": "events.jsonl", "format": "jsonl",
    "required": {"duration": "int"}
  },
  "analysis": {
    "path": "analysis.json", "format": "json",
    "required": {"decision": "str", "diagnostic_only": "bool"}
  },
  "data_roots": ["micro_analyze:P"],
  "cases": [
    {"name": "reopen", "fixture": {"duration": 8},
     "expected": {"decision": "reopen", "diagnostic_only": true}},
    {"name": "close", "fixture": {"duration": 12},
     "expected": {"decision": "close", "diagnostic_only": true}}
  ]
}
```

The packet supplies `report_fixture.py` with `generate(output, parameters)`.
It writes synthetic sample files under `output`, and may prepare scratch-only
files needed by the report. All generator and analyzer imports/execution run
under the same guard. Symbols must be in Python files beside the entry;
module collisions fail. Optional `data_roots` redirects existing module data
attributes to the scratch root, without replacing report functions. The
generator must not call native programs or read real samples/models.

Every sample must satisfy `samples.required`. The published object must satisfy
`analysis.required` and the case's exact `expected` values. Supported field
types are `str`, `int`, `float`, `bool`, `list`, and `dict`; booleans do not count
as integers. Fields beyond the required subset are allowed. The real analyzer
must execute, the returned and published objects must agree, and every case
must pass. Include each meaningful decision tail; the contract is a declared
schema/decision gate, not automatic discovery of all analyzer branches.
Contracts are at most 64 KiB, with 1–16 unique cases. Unknown contract fields,
invalid paths, missing fields and malformed contracts fail closed. Errors show
fixed diagnostic messages, never arbitrary packet exception text.

Compatibility: the exact original packet162 analyzer (SHA256
`9b25fa2bc8479c889cf5d530736114eb6fd7d657cade15a98d7ab01bafa87023`)
retains its existing fixture, reopen/close checks and identical receipts without
a contract. Other schemas without one return
`missing report contract for standalone micro schema`. An explicitly named
missing contract fails even for the legacy analyzer. Packet166 currently has
no contract; its frozen packet is not changed by this ops update.

## One-card windows

The fixture uses the actual `views.bracket(candidate)` and prompt list to
calculate request count. For bracket reports, `arm_order` and `max_new` come
from `plan.entry_rehearsal.window`, or from `READY-FOR-DEVICE.json` beside the
entry or in its parent packet. This reads declarations only; READY does not
authorize anything. A declared arm order must match the packet's actual order,
and the resulting report must agree with the declared cap (1–512 tokens).
With no cap declaration, historical 64-token smoke / 128-token bracket and
record fixtures remain unchanged.

The existing six-arm publication-split stream has a compatibility fixture in
`rehearse_report_adapters.py`, adapted from packet58aq's `report_adapter.py`.
It supplies synthetic decode/prefill timing rows; the real packet analyzer,
driver, window and queue publication code still run. Packet58aq's declaration
selects 32 tokens and six views (72 requests). Other additional diagnostic
stream schemas still need a fixture; varying view count alone does not invent
their timing fields. This shared check exercises the build-brief branch;
packet58aq's private suite remains the gate for all its other decision tails.

## One-card chain generator

`onecard_chain_derive.py` turns a winning one-load v5 bracket, a READY parent
one-card chain orchestration and a changed flag/binary into a sealed chain
packet plus orchestration that `fn-run/onecard-chain.sh <packet> <orch> --check`
accepts (packet172; see `notes/2026-10-19-own-runtime-packet172-ops.md`).

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/onecard_chain_derive.py \
  --parent-orch experiments/own-xpu-runtime/ops/packet58aj-orchestration \
  --packet experiments/own-xpu-runtime/stage2/<new-chain-packet> \
  --out experiments/own-xpu-runtime/ops/<new-chain-packet>-orchestration \
  --unit packet58-onecard-<tag>-a --output evidence/card0-<tag>-a \
  --flag wait-policy=spin --binary <device own-rt-iq3> --host-binary <gnu-host own-rt-iq3> \
  --bracket-summary <bracket packet>/screen/evidence/<v5>/resident/WSCREEN/summary.json \
  --threshold-file scripts/packet58_onecard_record_threshold.json </dev/null
```

Order, and fail-closed refusals (exit 2, created dirs removed, no READY):

1. Bracket: `passed`, `candidate_beats_all_controls`, `control_drift_passed`
   with drift <= 3%, five views, every request `exact_oracle`, and a passed
   WSCREEN `window.json` (its boot id is rechecked at launch).
2. `--help`: the device binary (in the Landlock `entry_sandbox`, no `/dev/dri`)
   and the host build must both list every flag. A flag that is missing while the
   bracket packet's `native/bracket_table.hpp`, `views.py` or
   `runtime-selection.json` names the dimension is refused as
   **bracket-table-only** (the packet58asc failure: chain windows cannot use a
   bracket table; add a native CLI option as in packet58asd).
3. Real parser: for KD/W2m/WS/WS128x/WS128 the copied `suite_driver.native_command`
   argv (flags appended) must pass the host build's `--p58r-parse-test`; an
   invalid value must be refused and the argv without the flag must still parse.
   K1a/K1b keep the parent's fixture binary.
4. Seal (`seal.py --verify`), `verify_ready.py` (calls the parent harness's
   `window.build_gate()`, oracle binding, pins, fresh output, bracket digests and
   boot), a temporary `lanequeue plan`, then both READY markers last.

The new packet gets the parent packet's top-level harness plus `selections/`,
`frozen-inputs/`, `host-admission/` and `native/`, with only the packet name,
unit, output and fault-review names rewritten. `seal.py` and `verify_ready.py`
are generated; the parent's own versions are packet specific. `--packet` and
`--out` must not exist.

Pin-guard hygiene (packet172b, after the packet58as-b/58asb refusals):

- The `--packet` prefix (text before the first `-`, `packet<digits><letters>`)
  must not match any existing `stage2/<prefix>-*`, `ops/<prefix>-*` or
  `ops/lane-queue/proposed-p<number>-*`, and `--out` must be
  `ops/<prefix>-<label>`. The pin guard globs `ops/<prefix>-*` into the packet
  closure; `packet58as-b-confirm` pulled in `packet58as-orchestration`. The
  refusal suggests a free prefix.
- No copied or generated manifest may pin the parent packet. Before sealing,
  every manifest that `pin_guard.collect_pins` reads (found by wrapping
  `read_metadata`, plus the inherited gate receipts) is rewritten: a parent pin
  is repointed to this packet's copy only when it has the pinned bytes,
  otherwise it becomes `{name, parent_relpath, parent_digest}`; a sub-bundle
  seal (`host-admission/seal.json`) is re-bound only for siblings this run
  rewrote. Shared immutable pins (packet49 oracle, models, other packets'
  frozen binaries) stay. Each change is in `evidence/pin-relocation.json`
  (a sealed gate); the final audit refuses any remaining parent or mutable
  cross-packet pin, then the temporary `lanequeue plan` runs the real guard.
- Runtime selection (packet172c, after the packet58asb launch failure):
  `runtime-selection.json` and the `views.validate` literal are both generated
  from `selection_extra(flags)` (`views.py` gets `dict(**GENERATED_RUNTIME_SELECTION, ...)`),
  as packet58as did by hand. A pre-device rehearsal then runs every chain
  window's real `window.main` (queue_runner `--plan` argv, recorded oneAPI
  path) on CPU up to its device boundary: K1a/K1b at output creation,
  KD..WS128 at the previous-window prerequisite. Priority, affinity and the
  user-unit cgroup are simulated; `validate(view)`, `build_gate`, memory plan,
  storage, fault-review parsing and the fault latch run for real. Standalone:
  `onecard_chain_derive.py --predevice-check <packet>`; receipt
  `ops/<prefix>-orchestration/predevice-rehearsal.json`.
- Runtime-read closure (packet172d, after packet58asb launch 2 stopped in KD
  post-processing on `lineage/fixtures/58c-supervisor/source-manifest.json`):
  the parent's `lineage/` and `screen-reader/` are copied byte for byte with
  the other copied dirs and sealed. `--closure-check <packet>` scans every
  non-test harness module for constant path joins under its packet/module root
  and `lineage/`/`fixtures/` literals; each one the parent has must exist in
  the derived packet (lineage/fixtures byte-identical; run outputs, build
  objects and lock files excepted). `--postnative-check <packet> [--evidence DIR]`
  runs each window's post-native report path (native receipt checks,
  `k1_summary`, `postload_observation` with the chain's own budget/memory
  records, native file hashing, summary save) on a temp copy of a completed
  chain's device evidence (default: the bracket packet's latest complete
  `evidence/card0-*`). The generator runs both before the lanequeue plan.
- A chain of the line that set the ledger's latest record is disclosed in
  `WINDOW.md`/READY as a confirmation run; the copied submission tool still
  refuses unless fresh WS128 beats that record.

`test_onecard_chain_derive.py`: refusal cases in a temporary root of symlinks;
the positive case derives into the REAL `stage2/` and `ops/` under a unique
`packet990t*` prefix (the guard resolves its own real root, so a temp-root
derive was checked against the wrong packet), runs the real pin guard,
`verify_ready.py` and `onecard-chain.sh --check`, and always removes the dirs
and asserts git sees nothing left.

## Regression checks

```sh
cd experiments/own-xpu-runtime/ops
nice -n 19 taskset -c 8-15,24-31 bash -c '
  ulimit -v 2097152
  python3 -B -m unittest test_rehearse_report_adapters \
    test_rehearse_entry.OnecardReportTest \
    test_rehearse_entry.MicroReportTest.test_packet162_report_and_all_entry_gates -v
' </dev/null
```

New contract fixtures live in temporary directories. The packet169 work note
records the seal scan, pre-change identity and byte comparisons. Frozen packet,
screen and live queue files are not updated by rehearsal.
