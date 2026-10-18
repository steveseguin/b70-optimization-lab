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
