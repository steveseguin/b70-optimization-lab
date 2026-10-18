# CPU drain-fix guard — 2026-10-18

New bundles now have a read-only CPU check for the cooldown race that stopped
packet103's WS window. The loop can cross its deadline during `check()`, so
the later sleep argument must be clamped to zero. The background and failed
window remain in the [race note](2026-10-18-own-runtime-packet103-chain-a-ws-drain-race.md).

[`scripts/check_drain_fix.py`](../scripts/check_drain_fix.py) accepts a packet
directory or `--all` for the complete stage2 tree. It finds every
`drain_gate.py` and text files containing the deadline subtraction, including
other filenames, hidden and ignored files. It parses source without importing
or executing it. The check recognizes outer `max(0.0, ...)` and equivalent
inner clamps such as `min(.25, max(0, until - now()))`, including reversed
`max` arguments and multiline calls. It also checks `time.monotonic()` forms.
Every relevant sleep in a file must pass. Redefined clamp names, unsupported
expressions, malformed candidates and an unrecognized `drain_gate.py` fail
closed. Python comments and string examples alone are not executable calls.

The scanner skips binary content, `.git`, `__pycache__` and traversal through
symlink directories. It is a static check for these cooldown expressions,
not a proof of arbitrary Python behavior or a dependency-closure audit.
Non-Python text candidates are retained as UNFIXED with an explicit reason;
the report therefore distinguishes an unparseable receipt from a known
unsafe sleep. No source text is copied into the report.

The [policy](../experiments/own-xpu-runtime/ops/lane-queue/LATCH-POLICY.md#drain-fix-check-before-chain-readiness)
requires this check to pass during every new bundle's CPU preparation, before
any chain readiness. Frozen bundles remain frozen. A failing bundle needs the
other lane paused during its chain; queue spacing cannot protect the internal
window transitions. The checker does not change pause markers or queues.

## Snapshot and validation

The [all-packet report](../experiments/own-xpu-runtime/ops/drain-fix-report.json)
records 100 candidate paths: **12 FIXED / 88 UNFIXED**. Of the 64 files named
`drain_gate.py`, **3 are FIXED / 61 UNFIXED**. The broader count includes other
cooldown implementations and one unparseable saved packet103 WS crash log.
Packet118's `drain_gate.py` is UNFIXED. Each readable candidate has its source
SHA256 and each recognized sleep has its line number. These are snapshot
results, not permission to run a chain. The scan exited 1 as expected.

Commands, from the repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s scripts/tests -p test_check_drain_fix.py -v < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B scripts/check_drain_fix.py \
  --all --json < /dev/null > experiments/own-xpu-runtime/ops/drain-fix-report.json
nice -n 19 taskset -c 8-15,24-31 python3 -B tools/check-pinned-hashes.py \
  --quiet < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B tools/check-pinned-hashes.py \
  --quiet --historical-manifest audits/repository-cleanup/2026-10-10/pin-audit.json < /dev/null
```

All 11 unit tests pass using local fixture files and temporary packet trees.
They cover nested/alternate filenames, ignored and hidden files, multiline
and parenthesized clocks, mixed safe/unsafe sleeps, misplaced clamps,
shadowed builtins, comments/strings, missing candidates, scan failures,
CLI exit codes and JSON, `--all` selection, and unchanged scanned bytes.

The required raw pin check exits 1: 318 pins, 87 matches, 231 historical
mismatches and no missing targets. The retained audit-manifest check passes:
230 recoverable histories, one explicitly blocked history, and five maintained
verifier identities match. No historical pins were rewritten.

Work stayed on `main`. The initial `git pull --rebase` refused unrelated dirty
orchestration files; `git fetch origin` confirmed HEAD and origin/main both
at `c06bd6a0f8b965231fef2b5706998ac0c9c99407` before edits. No existing packet,
GPU job, service, live queue, coordination record, sudo or host setting was
changed. Only the checker, tests/fixtures, policy, report and this note belong
to this change.
