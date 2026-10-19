# Lane queue storage admission and continuation

The queue now checks root free space during planning and again after review
and waits, immediately before START. A job needs its planned writes plus
25,000,000,000 bytes free. A refusal saves the byte counts and a queue-owned
receipt, emits `REFUSED-PREDEVICE` and an alert, drops dependent rows, and
continues to an independent job. It never retries the refused job.

Only queue/review code and new ops tests changed. No drivers were restarted,
no live queue files or packet trees were edited, and no GPU, model, service,
sudo or settings work was performed. The coordinator still owns driver
replacement between jobs. This change does not reduce packet reservations or
turn measured past writes into future storage budgets.

## Reservation policy

- An optional proposal `planned_write_bytes` is a nonnegative integer.
  The same declaration in proposal `plan` or `admission` is supported.
- Otherwise, the successful packet CPU plan's `planned_write_bytes` supplies
  its reservation. Planning returns the admission snapshot; the driver checks
  that reservation against fresh root free space immediately before START.
- The read-only per-packet lookup verifies `screen.py` and the selected
  `configs/<variant>-<kind>.json` (or explicit `--bracket` file) against
  `cpu-seal.json` source hashes. Literal profile `WRITES` values and the
  selected view count provide an offline reservation without importing packet
  code. Unavailable/nonliteral values use the fallback; changed pins refuse.
- The conservative fallback is **1,100,000,000 bytes per view**, five views
  for `--kind bracket` or `--bracket`, one otherwise. An explicit positive
  `--views` count or a sealed configuration supplies the view count. These
  are budgets, not measured write sizes. Byte units are decimal GB, matching
  the packet's existing 25 GB floor.
- CLI `plan` writes a separate plan-refusal receipt and emits the refusal and
  alert without consuming queue rows. `run` uses the existing pre-START
  refusal and dependency continuation path. Neither introduces a retry.

The hourly review prints root free bytes/GB and the largest pending job
reservation across both queues, with its source and job name. Inflight jobs
are excluded. Unreadable declarations are reported as unknown. The snapshot
is informational: it neither reserves disk nor sums simultaneous lane writes.
The packet's own storage gate remains in force for races after admission.

## Packet150 replay

At **2026-10-18 23:44:02.762101 UTC**, lane B emitted START for
`packet150-split-bracket-B`. It emitted `REFUSED-fast` at
23:44:05.750329, followed by the lane-stopped alert. The job lasted
2.735961 seconds and exited with status 1. Its journal ends the traceback
with `ValueError: bracket would breach 25 GB free-storage floor`.

The screen refused before creating its output directory or `window.json`.
The saved process observation had no device FDs or live children, but it
included `fd observation unreadable: 1764582`. That made the generic
pre-device proof reject it. The new storage-specific path accepts this
explicit floor refusal with absent/nonexecuted windows, while retaining the
ordinary-exit, clean fault count, released marker and drained-state checks.
It tolerates only the FD-read observation errors seen in this exited-process
case. Observed device FDs, live children, other observation errors, conflicting
or malformed window receipts, fault changes and signal exits still stop.

The driver reads the failed unit's journal only between this attempt's start
and end timestamps, since the systemd-run log itself contains only manager
status. It saves the refusal text, its hash, window receipt hashes and process
observations in a queue-owned `.storage-refusal.json` receipt. Packet evidence
is never manufactured or changed.

The regression fixture preserves the original three events, terminal queue
record, exit receipt and unit journal:
[test_storage_packet150.json](../experiments/own-xpu-runtime/ops/lane-queue/test_storage_packet150.json).
Sources were `events-B.jsonl`, `done-B-reviewed-20261018T234515Z.txt`,
the `packet150-split-bracket-B-d48fbdfe4b4f4e1ca7882b4a56f83150.exit.json`
receipt and that unit's journal from 23:44:02 through 23:44:06 UTC.
The replay uses temporary queues and fake execution. It now records
`REFUSED-PREDEVICE`, `SKIPPED-DEPENDENCY`, then `DONE` for the independent job.
The historical record stays unchanged.

## Verification

All checks ran with `nice -n 19 taskset -c 8-15,24-31`, `python3 -B`, stdin
from `/dev/null`, and a 2 GiB process address-space limit for Python test
runners. No packet plans or model reads were executed against live packets.

- Lane queue discovery (`ops/lane-queue/test*.py`): **176 passed**, including
  15 new storage tests and the existing plan, admission, refusal and pin tests.
- Review discovery (`ops/test_gpu_time*.py`): **25 passed**.
- Existing `stage2/screen/v4-lanes/test_plan_admission.py`: **3 passed**.
- Existing `stage2/screen/v5-bracket/test_plan_admission.py`: **3 passed**.
- Focused storage rerun after strengthening the plan/launch integration
  tests: **15 passed**. Both real planning admission and the fresh pre-START
  recheck are exercised with fake jobs and disk snapshots.
- `git diff --check`: passed.

Tests cover an exactly sufficient admission, a one-byte shortfall, declared
and default reservations, sealed view counts and changed pins, planning
receipts without queue edits, disk depletion during review, dependency
skipping, and the historical refusal. Negative replays retain lane stops for
device work, live children, unrelated errors and signals.

A read-only lookup of the actual packet150 proposal resolves **5.5 GB over
five sealed views**. A review-line smoke check saw **31.287 GB free** and no
pending reservation apart from the excluded inflight row. These are snapshots,
not admission for a later launch.

Git pull refused the unrelated dirty orchestration tree. Fetch confirmed
HEAD equalled origin/main before work and again before committing. Only the
explicit task paths are committed; shared orchestration edits remain outside
this change.
