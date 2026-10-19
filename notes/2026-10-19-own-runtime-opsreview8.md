# Opsreview8: proposal gate identity rehearsal

The shared entry rehearsal now catches stale job names and lane refusals before
a proposal reaches a device window. Both default and `--report` modes include
the `gate_identity` packaging check and use it in the overall verdict.

The check parses Python files throughout the proposal's packet tree, including
unimported coordinator/readiness gates that the existing device/report source
walk omits. It prunes every `lineage*` directory and does not follow symlinks.
It never imports or executes a packet gate and reads no model data.

Complete job names are compared with the proposal name. Complete unit names are
compared with lanequeue's `screen-<name>` unit, allowing its `.service` suffix.
Definite rejecting lane assertions and simple raising guards fail. Unknown
boolean operands remain unknown; normal lane dispatch is not treated as a
definite refusal. Source locations and reasons are returned without echoing
arbitrary source strings or exception messages.

This is a conservative static check, not a control-flow proof. Dynamic strings,
embedded command/message strings, proposal-construction data, mock-based CPU
fixtures and conditional lane checks produce warnings when their role cannot
be established. Obvious source directories and file names are not unit names.
Warnings preserve a passing admission verdict; they are visible in text output
and in the JSON `warnings` list. A definite mismatch always fails the check.

## CPU validation

All 43 rehearsal tests pass, including eight new identity tests:

- `git show a032d73a6^:experiments/own-xpu-runtime/stage2/packet58ai-miss-census/coordinator_gate.py`
  produces two foreign-job failures against the current census proposal. The
  fixed coordinator gate has no identity refusals.
- Packet151's actual `v5/readiness.py` is FAIL for lane A and PASS for lane B.
- The current packet58ai census, packet151 smoke/bracket B, packet153 smoke B
  and packet154 smoke B trees have passing identity admission verdicts. Their
  remaining unclassified uses are reported as WARN, not silently ignored.
- Both rehearsal modes fail overall on a rejecting identity assertion, even
  when native entry and report checks pass. JSON and text diagnostics retain
  the named packaging check.
- Exact names, both unit forms, service suffixes, boolean lane assertions,
  raising guards, dynamic fragments, unimported gates, lineage pruning,
  symlink exclusion and source-text redaction are covered.

Two existing test details were repaired: the packet58ai storage test now pins
its negative source to `60a56785a^` and checks that today's source passes; the
private packet58v fixture resolves the lanequeue source path so the same test
works from a temporary checker copy.

The candidate and tests were edited in a private sibling directory under
`experiments/own-xpu-runtime`, with unchanged helper modules copied there and a
read-only-use symlink to the real lanequeue. The complete test command was:

```sh
nice -n 19 taskset -c 8-15,24-31 bash -c 'ulimit -v 2097152; python3 -B -m unittest discover -s experiments/own-xpu-runtime/.opsreview8-ps0TAh -p test_rehearse_entry.py -v' </dev/null
```

After the tests passed, the live checker and test file were each replaced once
by atomic rename, after checking that their original hashes had not changed.
To repeat the suite after installation, use the same command with the test
directory changed to `experiments/own-xpu-runtime/ops`.

No GPU job, service, sudo command, host setting, packet tree or live queue was
changed. Only the shared checker, its tests and this note belong to this work.
The initial fast-forward pull refused because another local commit and the
remote had diverged; concurrent repository synchronization subsequently brought
HEAD and origin/main to the same commit, verified before installation. No
unrelated working-tree changes were staged or discarded.

## Packet162c — standalone-micro report adapter

Added a report adapter selected by `plan.entry_rehearsal.kind == "micro"`
or the entry filename `run_micro.py`. It imports the actual entry with the
existing report I/O guard already installed, uses the real argument parser,
and invokes its unchanged `report_completed(output)` function. Main and
device admission are not executed. Other report paths retain their behavior;
storage, deadline, preparation and identity gates remain mandatory.

The supported report contract is the packet162 event-stream schema and
`micro_analyze.P` data root. Unknown schemas fail closed. Two invented complete
streams exercise the 0.85 reopen boundary and a 0.86 negative result. Only the
analyzer's writable data root is redirected to scratch. The adapter checks
the returned/persisted report, input hash, diagnostic/quality labels and the
negative index's evidence link. Its receipt explicitly marks synthetic evidence,
no device execution and parser/report-only execution.

Validation: **47 tests pass in 32.357 seconds**, including all 43 existing
tests and four new micro tests. The new tests cover packet162's complete entry
checks, explicit micro selection under a different filename, raising/no-op
broken report functions, and sticky I/O denials for model/device reads, child
execution and outside writes. No exception text is leaked.

The checker, tests and unchanged helper copies were tested in the private
`.packet162c-bxv4k5b2` sibling directory, with a read-only-use link to lanequeue.
After all tests passed and the live originals' hashes still matched, the checker
and tests were each installed once with atomic rename. The suite can be repeated:

```sh
nice -n 19 taskset -c 8-15,24-31 bash -c 'ulimit -v 2097152; python3 -B -m unittest discover -s experiments/own-xpu-runtime/ops -p test_rehearse_entry.py -v' </dev/null
```

Packet162's own seal then repeated the live entry/report, seven analyzer tests,
prepared artifact checks and temporary queue plan successfully; READY is true.
Its existing `analyze.limits()` requests 4 GiB, so the invocation clamped only
`resource.setrlimit(RLIMIT_AS, ...)` requests to the already enforced 2 GiB cap.
No packet source or qualification function was patched. The exact invocation
was the following Python body under `nice -n 19 taskset -c 8-15,24-31 python3 -B -c`,
with `ulimit -v 2097152` and stdin `/dev/null`:

```python
import pathlib, resource, runpy, sys
from unittest.mock import patch
path = pathlib.Path("experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/seal_micro.py").resolve()
sys.path.insert(0, str(path.parent))
sys.argv = [str(path)]
original = resource.setrlimit
cap = 2 * 1024**3
def bounded(kind, limits):
    if kind == resource.RLIMIT_AS:
        limits = tuple(cap if v == resource.RLIM_INFINITY else min(v, cap) for v in limits)
    return original(kind, limits)
with patch.object(resource, "setrlimit", bounded):
    runpy.run_path(str(path), run_name="__main__")
```

[Packet162c result and retained receipts](2026-10-19-own-runtime-packet162.md#packet162c--shared-micro-report-adapter-installed-and-micro-resealed).
No GPU, service, sudo, settings, live queue or model-file access. Unrelated
working-tree changes were preserved.
