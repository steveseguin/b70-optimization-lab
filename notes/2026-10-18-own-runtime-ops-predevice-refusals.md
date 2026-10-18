# Queue admission waits and proven pre-device refusals — October 18

The queue now waits for a job's declared host-memory requirement plus 1 GiB
before START. It waits at most twenty minutes, honors pause/stop and fault
guards, and records the shortfall. It changes no host settings. A proven
pre-device refusal now drops that job and its queued dependencies, raises an
alert, and lets the driver reach the next independent job. No refused job is
retried. Possible device work, new faults, latches, retained markers and
unfinished teardown still stop the lane.

Only `ops/lane-queue/lanequeue.py` changes operational behavior. Frozen wrappers
are unchanged. The coordinator restarts drivers between jobs; this work starts
or stops no services and changes no live queue, event, done, inflight, PAUSE or
coordination file. CPU commands use nice 19, CPUs 8–15/24–31, Python `-B` and
stdin `/dev/null`. No GPU, sudo or settings operations were used.

## What the original receipts actually establish

- The archived packet58r run's `WSCREEN/window.json` says
  `device_executed: false`, but its enclosing `queue.json` says true and lists
  completed K1a/K1b stages. Both K1 receipts say `device_executed: true`.
  Therefore this **whole job** cannot be reclassified as pre-device. The new
  admission wait runs before those fixtures, using the plan's full
  118,308,908,048-byte requirement, plus 1,073,741,824 bytes of queue headroom.
  Evidence: [archived packet58r queue](../experiments/own-xpu-runtime/stage2/packet58r-onecard-v5/evidence/refused/card0-v5-a-host-admission-20261018T150354Z/route-rec/queue.json).
- The archived `p131-B-smoke12` done record reports 0.3164 seconds, ordinary
  exit 1 and unchanged fault count 2, but no `window.json` at its exact queued
  output path. Its captured systemd-run log supplies no job refusal receipt.
  These facts alone remain insufficient. No historical done record is changed
  and no exception is inferred from the reported unsafe-identity error.
  Evidence: `ops/lane-queue/done-B-reviewed-20261018T150636Z.txt` and
  `p131-B-smoke12-c55d0164aa3745409e2ab309e017e4c0.log` (host-local evidence).

The new continuation gate requires fresh job receipts **and** observed unit
PIDs with no device fds, no observation gaps/errors, no remaining PIDs, a clean
journal comparison, no lane marker, no latch and no unfinished teardown.
Any earlier executed child window rejects the entire job's exception. Missing
or ambiguous evidence still stops. This intentionally does not claim the
historical packet131 refusal is automatically recoverable with frozen wrappers.

## Implementation and checks

Memory bounds come from CPU-plan JSON or proposal plan/admission fields, with
packet JSON memory budgets as a fallback. Bounds are checked again after
preparation and immediately before launch. The deadline survives repeated
preparation attempts. No inflight record or START is written during the wait.

`REFUSED-PREDEVICE` retains return/status codes, receipt hashes and PID/fd
observations. Dependency pruning uses both queues under ordered edit locks,
preserves newly appended independent work, follows explicit `depends_on`
transitively and recognizes a same-packet smoke prerequisite. Skipped rows
have durable `SKIPPED-DEPENDENCY` records; an already-running dependent is
never removed. Old failures cannot be hidden by a later skip, and all done
names remain protected from replay. The existing ninety-second gap remains.

CPU validation:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/ops/lane-queue -v < /dev/null
```

**129 tests passed.** Fake meminfo covers recovery, exact headroom, the full
1200-second deadline, malformed input, reordering and interruption. Fake
receipts, markers, cgroups/fds and fault counts cover valid refusal continuation,
cross-lane/transitive dependency removal, retained inflight dependents, observed
device work, prior K1 work, missing/malformed/unreadable evidence, signal exits,
latches, unfinished drains, no replay and restart behavior. Existing queue,
drain-spacing, live-overlap, report-failure and environment tests also pass.

## Read-only live-queue planning

At about 15:13 UTC the two queue files were read into a temporary directory;
the real CLI `plan` ran against those copies only. The edit locks it creates
were temporary, never the live locks.

| Lane | Snapshot rows | Plan result |
| --- | ---: | --- |
| A | 2 | `packet58r-v5-A`: refuses because its output directory already exists; `packet58t-resident-A`: passes with required available bytes 118,308,908,048 |
| B | 0 | Empty queue; exit 0 |

A snapshot SHA-256:
`d6b4f1a43866ed4eeb9c6ac97c475c3afb3c1914c56b90937bc4e8f983bff7ec`.
B snapshot SHA-256:
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
The existing A output was preserved. These are queue-plan observations, not
device runs or permission to replay existing output.

`git pull --rebase` refused unrelated dirty orchestration files. `git fetch`
then confirmed main HEAD and origin/main both at
`a98ba1eec6ed66ed2350a52911992b4ee6f6267f`. Only the queue implementation,
its tests, latch policy and this note belong to this change.
