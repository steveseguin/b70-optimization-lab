# Coordinator handoff

No device authorization is exercised by CPU preparation. The proposed job is
[`ops/lane-queue/proposed-p77-B.txt`](../../ops/lane-queue/proposed-p77-B.txt).
It has been planned on a temporary copy, not added to either live queue.

From the repository root, recheck the fixed selection on CPU:

```bash
P=experiments/own-xpu-runtime/stage2/packet77-attribution
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/run_screen.py" --plan </dev/null
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/queue_plan.py" </dev/null
```

Expected device work: about **420 seconds**, including one load and both arms.
This is a planning estimate; lane holds and admission waits are additional.
The inherited cooperative watchdog is **3,600 seconds**, exceeding 4× the
estimate. There is no retry, restart loop, resident server or submission.

The coordinator may place the proposed line into its approved lane-B queue.
The queue provides a fresh fault-review receipt, the closed environment and an
admitted `screen-*` user unit: nice 0, cores `4-7,20-23`, `Restart=no`,
`SendSIGKILL=no`, `KillMode=process`, `ExitType=cgroup`, `TimeoutStopSec=infinity`.
The wrapper uses the existing lane-B ownership, memory, STOP, fault, whole-host
timing-hold and shared drain rules without changes. A device run can still
refuse admission; CPU planning does not grant permission or waive a live gate.

The fixed fresh output is:

```
experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/packet77-attribution-B-a
```

After successful drain and lane release, the packet entrypoint writes:

- `run/attribution-summary.json` and `.md`: current per-rank tables, outside
  split, ranked levers and paired overhead.
- `run/{control,attribution}/summary.json`: separate diagnostic suites.
- `run/{control,attribution}/<prompt>/rank{0,1}/sites.jsonl`: raw events.
- `run/paired-inputs.json`: both arms' exactness receipts staged before drain.

Shared v4's ordinary summary covers the attribution arm; the paired report is
the authority for overhead and class attribution. Check for
`packet77-report-failure.json` and the queue return code as well as `window.json`.
A packet-specific report failure occurs after release, retains raw evidence,
and returns failure without poisoning the device lease. Repair reporting on
CPU; do not repeat the model run merely to regenerate a report.

```bash
R=experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/packet77-attribution-B-a/run
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/report.py" \
  --run "$R" --output "$R/attribution-summary.json" </dev/null
```

The paired fixture is not a realistic final performance gate. Target device
exactness and actual class costs remain pending until this run completes.
