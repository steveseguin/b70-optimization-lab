# Laguna — XCCL probe harness correction

Date: 2026-07-26 America/Toronto

Status: **tooling repaired and CPU-only validated; no XPU probe or recovery
action was run. Post-recovery collective health remains unknown.**

## Finding

`tools/run_xccl_collective_probe.sh` invoked:

```text
$scratch/xccl_probe.py
```

No tracked caller copied a file there. The committed probe introduced beside
the wrapper in `a02c4809c` is:

```text
tools/xccl_collective_probe.py
```

The mismatch existed from the wrapper's first commit. Every retained rank log
from these four attempts contains only Python's missing-file error:

- `probe-postreload`: 4/4 ranks;
- `probe-postflr`: 4/4 ranks;
- `probe-postshm`: 4/4 ranks;
- `ladder-preflight`: 4/4 ranks.

None contains `import-done`, `pg-initialised`, `tensor-allocated`, or
`all_reduce-done`. The displayed `0/4` was therefore “zero probe programs
executed or reached `import-done`,” not “zero collectives completed.”

This correction does not erase the independent pre-recovery evidence: model
runs at both candidate and approved-record commits hung during warm-up,
single-card operations reported device errors, and the kernel recorded a
timed-out job and GuC reset. It does mean that the retained wrapper runs cannot
establish current health or the effect of the later module reload, FLRs, or
shared-memory cleanup. Any unrecorded manual probe is outside the retained
evidence and is not reclassified here.

## Repair

The wrapper now:

- resolves and validates its sibling `xccl_collective_probe.py` before
  creating an output directory;
- launches that exact tracked source from any working directory;
- reserves exit 2 for pre-launch harness and argument failures;
- requires exactly one anchored marker for every stage and rank;
- reports the earliest classified boundary, distinguishing import, device,
  process-group, tensor, pre-collective, collective-stage, verification,
  teardown, and child-exit failures;
- returns zero only for four complete, verified, cleanly torn-down ranks;
- rejects rank/rendezvous environment overrides;
- validates labels and preserves existing same-label evidence instead of
  deleting it.

The post-reboot ladder now retains the wrapper output, requires the explicit
  `PROBE_RESULT=PASS clean_teardowns=4/4` marker, and no longer translates
  every nonzero return into “reboot required.”

## Validation

No Torch import, XPU operation, collective, process signal, privileged action,
or recovery command was used to validate this repair.

CPU-only validation passed:

- `bash -n` for the wrapper and ladder;
- Python AST parsing;
- Ruff lint and format checks;
- eleven CPU-only regression tests covering success from an unrelated working
  directory, missing sibling source, import failure, true collective-stage
  failure, failure before collective entry, missing verification, nonzero child
  exit, reserved-rank override, preservation/refusal of an existing output
  directory, and the ladder's non-prescriptive failure handling.

## Evidence boundary and next action

The host's post-FLR collective state is **unknown**. Do not perform a bus reset,
delete more shared state, launch the benchmark ladder, or claim recovery based
on the invalid attempts.

The next hardware action requires an operator decision: either take the
conservative clean-reboot path already supported by prior B70 recovery history,
or explicitly authorize exactly one reviewed run of the repaired minimal
collective probe. The tooling repair itself authorizes neither.
