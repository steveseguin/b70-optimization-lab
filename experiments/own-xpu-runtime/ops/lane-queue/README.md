# Per-lane device job queue

One CPU driver per lane replaces the coordinator's hand-written waiters. It
rereads `queue-A.txt` or `queue-B.txt` at every job boundary. Preparation and
tests start no services or devices. **This queue has not been started.**

The driver sets itself to nice 19 and cores `8-15,24-31`. Each device job gets
its own `screen-<name>` user unit, `systemd-run --wait`, nice 0, the exact lane
CPU affinity, and these properties:

```
Restart=no SendSIGKILL=no KillMode=process ExitType=cgroup
TimeoutStopSec=infinity WorkingDirectory=/home/steve/llm-optimizations
```

Lane A uses cores `0-3,16-19`; B uses `4-7,20-23`. Both `CPUAffinity` and
`taskset` enforce that placement. Screen commands run through `env -i` with
exactly `PATH=/usr/bin:/bin`, `OMP_NUM_THREADS=2`, and `LD_LIBRARY_PATH` taken
from the literal `P49_LDP` assignment in
`/tmp/claude-1000/-home-steve/fn-run/p49.env`. That file is parsed as data,
never sourced or printed. The driver's inherited environment cannot leak
into a screen.

## Job lines and planning

Each nonblank, noncomment line is a JSON object. Names must be unique in a
queue and must not reuse a completed job's name. Paths are absolute or relative
to the repository root. `argv` is an argument array, not shell text. Python
jobs must use `python3 -B script.py` to avoid writes to frozen source trees.

```json
{"name":"example-A","lane":"A","argv":["/usr/bin/python3","-B","path/to/screen.py","--lane","A","--output","path/to/fresh-output","--fault-review","{REVIEW}","--authorized-device-window"],"env_extra":{},"review":"path/to/fault_review.py"}
```

`review: null` is allowed when no review is needed. Otherwise the queue calls
that tool with a fresh `--output` and substitutes `{REVIEW}` in the argv. The
existing tools require their receipts under their own `evidence/` directories;
only an authorized **run** creates those receipts. Planning does not generate
reviews, read the journal, create evidence in packets, or launch systemd units.

For a reviewed coordinator shell script, use `script` instead of `argv`:

```json
{"name":"coordinator-A","lane":"A","script":"path/to/coordinator_probe.sh","env_extra":{"P49_LDP":"{P49_LDP}","FAULT_REVIEW":"{REVIEW}"},"review":"path/to/fault_review.py"}
```

`env_extra` is accepted only for coordinator scripts. Values go through
`systemd-run --setenv`; a small entry helper retains only the three standard
variables plus those explicitly named extras before invoking Bash. The
coordinator must use its own three-variable `env -i` when invoking a screen.
Extras never enter the direct screen command's environment. Shell scripts are
trusted coordinator code, not a sandbox; review their inner launch and output
paths before queuing them.

From the repository root:

```bash
Q=experiments/own-xpu-runtime/ops/lane-queue
python3 -B "$Q/lanequeue.py" plan --lane A
python3 -B "$Q/lanequeue.py" plan --lane B
```

Plan validates the executable, lane, environment, explicit output and fixed
quick-job output freshness. For Python jobs with an explicit argparse
`--plan`, it removes device authorization and review arguments and runs the
CPU plan, plus the sibling wrapper-seal verifier when present. Packet67's
seal verifier gets `--verify`, never its seal-creation mode. Every queued job
is checked; a failure produces a nonzero exit. Shell wrappers and executables
without a recognized CPU plan get an explicit **unsupported; static checks
only** report. They are never executed speculatively with `--help` or `--plan`;
that could start a device if the script ignores arguments. Their private
outputs and inner screen closure still need coordinator review.

## Convert the pending packet work

The complete JSON lines are in [examples/queue-A.txt](examples/queue-A.txt)
and [examples/queue-B.txt](examples/queue-B.txt). They translate these commands:

| Lane | Order | Source |
| --- | --- | --- |
| A | packet67 quick A, **only if not STOPped** | [packet67 WINDOW.md](../../stage2/packet67-roofline/WINDOW.md) |
| A | packet69 quick A | [packet69 quick commands](../../stage2/packet69-rank1-head/screen/quick/README.md) |
| B | packet69 attribution screen | [packet69 WINDOW.md](../../stage2/packet69-rank1-head/WINDOW.md) |
| B | packet69 quick B | [packet69 quick commands](../../stage2/packet69-rank1-head/screen/quick/README.md) |

The quick commands are in packet69's quick README, rather than its WINDOW.md.
Keep each packet's fixed internal job order; the outer queue reorders whole
jobs only. If packet67's `screen/evidence/STOP` exists, omit its job. Do not
remove STOP files, rename used output directories, or requeue a completed
screen to make a plan pass. A failed job needs coordinator review first.

The examples can be checked without installing a live queue:

```bash
Q=experiments/own-xpu-runtime/ops/lane-queue
python3 -B "$Q/lanequeue.py" plan --lane A --directory "$Q/examples"
python3 -B "$Q/lanequeue.py" plan --lane B --directory "$Q/examples"
```

To prepare queues, copy the reviewed example lines to `queue-A.txt` and
`queue-B.txt` beside the driver, omitting packet67 if stopped. No live queue
file is shipped. Commands below are for the coordinator, not preparation:

```bash
Q=/home/steve/llm-optimizations/experiments/own-xpu-runtime/ops/lane-queue
systemd-run --user --unit=lanequeue-A --property=Restart=no \
  --property=SendSIGKILL=no --property=KillMode=process \
  --property=TimeoutStopSec=infinity --property=Nice=19 \
  --property='CPUAffinity=8-15 24-31' \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/python3 -B "$Q/lanequeue.py" run --lane A
# Use lanequeue-B and --lane B for the other lane.
```

The empty queue waits for appended work. Use `STOP-A`/`STOP-B` to finish an
idle driver; it does not auto-launch any queue or restore a service.

## Edit, pause and stop

Use the matching **edit lock** for every queue write, including appends and
reorders, so a completion cannot overwrite a concurrent edit. For example:

```bash
Q=experiments/own-xpu-runtime/ops/lane-queue
# Prepare queue-A.next in Q, then replace it while holding the edit lock:
flock "$Q/edit-A.lock" mv "$Q/queue-A.next" "$Q/queue-A.txt"
# Append one reviewed JSON line from a file:
flock "$Q/edit-A.lock" sh -c 'cat "$1" >> "$2"' sh job.json "$Q/queue-A.txt"
touch "$Q/PAUSE-A"  # wait at the next job boundary
rm "$Q/PAUSE-A"     # resume only this queue pause
touch "$Q/STOP-A"   # exit at the next boundary, even while paused
```

The running line remains visible until completion. Edit pending jobs, not the
running job's contents. Removing a running line does not cancel the unit.
Uncooperative writes without the lock cannot be made race-free by a reader;
the queue does not claim otherwise. It rereads after planning/review and after
completion, preserving appended or reordered lines. SIGINT/SIGTERM also
request a boundary stop; the driver waits for its current unit to drain and
never kills or resets a GPU process.

## Refusal and completion rules

Before each launch the queue enforces the following:

- At least 90 seconds since the preceding queue job finished, including across
  clean driver restarts. Pauses and STOP are checked during that wait.
- Boot prefix `2cba7160`, exactly two fault lines, and readable complete kernel
  journal. `FAULT` and `DELETED` are extracted from the authoritative
  [window driver](../../stage1/packet4-prep/driver/window_driver.py), without
  importing it. A different boot or fault count stops for review; it never
  learns a new baseline automatically.
- No active marker for this lane in
  `/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1`.
  Live, dead and unknown owners all stop admission. A dead owner produces an
  explicit alert; the marker is never removed or archived automatically.
- No `stage2/screen/v3/fault-*` latch, including another lane's latch.
- CPU plan/output checks, a fresh review if required, and a second guard check
  immediately before launch. The existing sealed screens retain live fault
  supervision and graceful device teardown during their jobs.

The process return code is captured directly from `subprocess.run` before
reading clocks or querying status. `systemctl show` supplies `Result` and
`ExecMainStatus`. An `ExecStopPost` helper also saves those exit facts from
systemd's `SERVICE_RESULT`/`EXIT_STATUS` before transient-unit garbage collection.
If the unit has disappeared, that receipt is used immediately. There is no
`list-units` waiter. Missing exit evidence is a failure, not assumed success.

Every completed job moves to `done-<lane>.txt` as JSON with the original job,
rc, unit result/status and evidence source, UTC start/end, seconds elapsed,
review path, log path, and outcome. Nonzero rc under 10 seconds is
`REFUSED-fast`; any other nonzero rc, bad unit result, changed fault count,
marker or latch after exit also stops the lane. No failure starts the next
job. Alerts go to stderr/stdout and `events-<lane>.jsonl`; there is no external
notification or automatic retry.

The lane driver lock prevents a second driver in the same queue directory.
An `inflight-<lane>.json` is fsynced before launch and removed only after durable
completion and queue update. A crash, partial completion, or ambiguous launch
leaves it in place and refuses restart. A last failed completion likewise
refuses restart, even if someone appends new jobs. Inspect the unit, log,
receipt, markers and device teardown; preserve the records for review before
any manual recovery. The queue never clears these conditions itself.

## CPU verification

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/ops/lane-queue -v
```

Tests mock all systemd/journal/device work and exercise garbage-collected
units, closed environments, rc preservation, stale/live markers, latches,
fault changes, pause/stop, reordering/appending, the 90-second gap, fast
refusals, device failures and crash recovery. The example CPU plans check the
real frozen packet seals and fresh-output rules. The [validation receipt](validation.json) records 28 passing tests and all four
example plans, bound to source hashes. No live unit execution has been tested
in this preparation.
