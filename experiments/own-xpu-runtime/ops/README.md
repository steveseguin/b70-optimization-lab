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
