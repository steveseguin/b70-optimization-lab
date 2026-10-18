# Opsreview5: rehearse reports before device work

The shared entry rehearsal now accepts `--report`. Each proposal must pass
its native entry checks and two fresh CPU report processes: smoke and bracket.
The packet's real entry and argument parsers run with temporary outputs.
Admission checks and the previous-smoke prerequisite are replaced; report,
summary, token parsing and late report imports remain the packet's own code.
The screen's post-device block is selected from its source, supporting both
inline reporting and the factored `report_completed` form. Unknown layouts
fail rather than receiving a readiness pass.

Synthetic oracle tokens, request rows, boundaries, allocation receipts, draft
traces and empty timing streams are generated in scratch, then removed. No
recorded device result is copied. Static checks also reject duplicate Python
module/package names between the packet root and active import directories.
The harness removes its own helper modules from the child's import cache so
they cannot shadow packet helpers.

The oracle entry runs until its first evidence-read boundary to preserve its
preceding real imports and `sys.path` changes. Its live seal is not validated,
and later data-dependent imports are outside this gate. Packet142's regression
covers its root-path insertion and preloaded v5 build module. A different
layout/schema must add a tested adapter; this is not a universal Python-job
emulator or an arm-state-machine rehearsal.

Validation uses `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin
`/dev/null`, and a 2 GiB address-space limit. Report children enforce those
limits themselves, close stdin, use the lanequeue environment, and time out
after 45 seconds. Python audit checks deny device/model/data reads,
subprocesses and writes outside scratch; exceptions expose only types and
source locations, never arbitrary exception text. This is a trusted-source
harness, not an isolation boundary for hostile native code.

Tests reconstruct Python source and its import-time registry/environment directly with
`git show`, without checkout or worktrees:

- `3d08f0a2289b32e5bb892df60690287c12e4110b^`: the original smoke import fails;
  nine duplicated module names also block readiness.
- `3d08f0a2289b32e5bb892df60690287c12e4110b`: smoke and bracket complete.
- An unused synthetic collision blocks readiness even when reports complete.
- Attribute/schema errors, model reads, subprocesses and external writes fail.
- A failed report prevents a combined pass even if native checks pass.

Command: `python3 -B -m unittest discover -s experiments/own-xpu-runtime/ops
-p test_rehearse_entry.py -v` with the limits above. Git history reads use
per-command 16 MiB pack windows and a 64 MiB pack limit so the repository's
large pack stays within the test memory cap; no Git or host settings change.
All 13 tests pass. The live packet142 smoke proposal also passes the combined `--report --json`
CLI. No packet trees, live queues, GPU work, services or host settings changed.

## Opsreview6: one-card packet58 reports

`--report` now recognizes the packet58 `queue_runner.py` / `window as W`
entry layout automatically. It runs the real entry's imports and main argument
parser with its own import path, stopping before admission, planning or device
work. The window's actual child-command builder identifies `suite_driver.py`;
the driver report block, late compare import, window summary read/write/hash
block and WSCREEN queue decision block run unchanged against temporary evidence.
Only data locations point to scratch. No report or comparison function is mocked.
Queue persistence is suppressed; this does not rehearse the arm state machine.

Synthetic oracle tokens, input tokens, request timings, reset/view boundaries
and drained-owner receipts exercise the real token and metric readers. The
first view is deliberately slow. Packet58x/58ab exclude it from speed and drift
but still require its exact tokens; an injected A0 token mismatch fails. The
older packet58v policy retains A0 in its comparison and returns a negative
speed decision without failing report execution. These are invented test
numbers, never measurements or readiness evidence.

Packet58z is a record chain, with no smoke/v5 proposal pair in this tree. Its
adapter runs the actual `WS128x` and `WS128` window reports instead of inventing
screen stages. K1 fixtures, retained-layer diagnostic windows, admission,
postload memory observations and live oracle seals remain outside this report
gate. Each report runs in a fresh, bounded CPU process. The only additional
non-synthetic reads allowed are the packet's exact import-time `views.json`
and `admission.json` paths. Model/device reads, child execution and writes
outside scratch remain forbidden.

Validation, using `ulimit -v 2097152`, `nice -n 19 taskset -c 8-15,24-31
python3 -B` and stdin `/dev/null`:

- All 20 tests in `ops/test_rehearse_entry.py` pass, including the previous
  two-card historical regression. One-card tests cover packet58x/58ab smoke
  and v5 proposals, packet58z windows, real and unused import collisions,
  schema errors, forbidden I/O, A0 exact-token rejection and window reporting.
- Both packet58ab proposals pass the combined `rehearse_entry.py PROPOSAL
  --report` CLI: two native entries and both synthetic report kinds.
- Packet58z passes both synthetic window reports and the combined gate with
  its two device-entry binaries explicitly declared, using their build-receipt
  hashes and the fixture's explicit `K1 unknown option` parser expectation.
  Its automatic inventory also includes additional tools whose default help
  probes fail; no native inventory/parser rule was weakened.
- Live packet58v correctly fails a separate real import defect:
  `launch_identity.py` loads today's shared `lanequeue.py` by filename without
  making its sibling `pin_guard` import available. Nothing repairs that path
  in the harness. A private source-copy fixture supplies the missing import
  path solely to test packet58v's older report schema and comparison policy.

The requested note is the only change outside the rehearsal script and tests.
Packet files, live queues, READY files and unrelated dirty work were untouched.
No GPU, service, sudo, model read or host-setting change was used.
