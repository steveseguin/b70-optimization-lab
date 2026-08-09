# Canonical Q8 Phase-1 harness-only failure

Date: 2026-08-09

## Classification

The first live Phase-1 launch failed closed before GPU 1 was launched. This was
a harness-control failure, not a model result. It produced no sequential oracle,
correctness comparison, throughput result, or promotion evidence.

Failed packet:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/canonical-q8-c1-oracle-four-gpu-20260809T231356.039564924Z`

The packet remains hash-sealed, intact, and exhaustive. Verification from
inside the run directory passed for every entry in `wave-artifacts.sha256`.

- artifact-manifest SHA-256:
  `5178839c6fe76e0733fafb617212983143530f971eb6f9a2291b247c779d8791`
- detached failure-marker SHA-256:
  `a72cc59aab917edcd1c1417d7061000c3ce73e537cf8d25c5fccf646be256127`
- marker classification: `diagnostic-only-failure`, `evidence_valid=false`

## What happened

GPU 0's isolated child and llama-server were healthy and still in the recorded
session when the outer runner claimed `prior child 0 vanished during stagger`.
The retained pre-drain process table shows child PID 393423 and llama-server PID
393893 in PGID/SID 393423. The server was still loading normally. The outer
runner published its abort; the child observed it during readiness and exited
through the failure path.

The false vanish was caused by Bash expansion order in three helpers. A single
`local` command both assigned `gpu="$1"` and indexed arrays with `$gpu`. Those
array expressions used the caller's/global `gpu` value before the new local
value took effect. While the outer loop was preparing GPU 1 and checking
`prior=0`, `owned_child_group 0` therefore looked at the empty GPU 1 entry.
The same latent defect existed in `recorded_session_alive` and
`signal_recorded_session`.

A separate return-code bug made the cleanup report inaccurate. After a
no-match `if pipeline; then ...; fi`, the function read `$?` after `fi`; Bash
returns zero for that no-branch `if`, so `recorded_session_alive` reported a
session alive even when its process-table scan found no members. The server's
log records TERM cleanup beginning at 19:15:23.835 local time, about 35 ms after
the retained drain-after table. The outer runner then waited the full 90-second
TERM and 10-second KILL windows and recorded `forced_kill=1` and
`cleanup_survivor=1`. Those fields are untrustworthy and overreported because
the broken predicate continued to return alive after every successful process
query. Whether KILL had a live target is indeterminate because there is no
membership snapshot at the exact escalation instant. The empty post-cleanup
scans prove the final survivor, listener, relevant-process, and device-fault
state was clean.

The sealed post-cleanup SID-member, listener, and relevant-process files are
all empty. The device-error scan is empty. `failure_passive_scan_rc=1` came from
the expected abort text in `gpu0-runner.log`, not from an xe/device fault.

## Fix and regression coverage

The narrow fix:

- separates argument-local assignment from all dependent array lookups in the
  three session helpers;
- captures the no-match pipeline status inside `else`, treating exact rc 1 as
  no live member and process-query errors conservatively as still alive;
- makes the outer runner wait a default 20 seconds (floor: 15 seconds) beyond
  its own 60-second passive interval before session TERM, providing a bounded
  child handoff window without claiming when every child began its local drain.

Offline behavioral tests execute the exact extracted shell helpers with a
caller/global GPU different from the requested GPU. They cover the owned-child
lookup, live/no-member/query-error session results, requested-SID signal
selection, and the handoff safety floor. No GPU, XPU query, or live server was
used while diagnosing or fixing the harness.
