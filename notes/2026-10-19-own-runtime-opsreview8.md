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
