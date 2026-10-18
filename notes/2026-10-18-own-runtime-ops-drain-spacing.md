# Queue launch spacing after shared teardown — 2026-10-18

The queue now waits until 61 seconds after the latest completed shared teardown
on the current boot before starting a job. This keeps a recently completed
teardown from sending queued jobs into the frozen wrappers' faulty 60-second
sleep loop. The [packet103 incident](2026-10-18-own-runtime-packet103-chain-a-ws-drain-race.md)
records that race and its refused start. No frozen wrapper was changed.

Only [lanequeue.py](../experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py)
changes executable behavior. After CPU planning/review, it reads
`experiments/own-xpu-runtime/stage2/screen/v3/teardown-state.json` and requires
an exact current `boot_id`, `drained is True`, and a finite nonnegative numeric
`completed_monotonic` before adding spacing. Python's `time.monotonic` uses
Linux `CLOCK_MONOTONIC`, matching the writer. Old or other-boot state adds no
wait. Unreadable, malformed, missing or undrained state leaves the existing
admission path in charge; this helper grants no wrapper exception.

The wait checks the existing journal, marker and latch guards, honors
PAUSE/STOP and boundary-stop signals, and rereads the teardown on every poll.
`WAIT-DRAIN-SPACING` records the job, remaining `wait_seconds`, and
`until_monotonic` for each new deadline. Sleeps are capped at one second and
clamped after guards/logging, so slow checks cannot cause a negative sleep.
Each wait has a 120-second budget; a still-pending deadline then refuses launch
without writing inflight state. Individual journal reads retain the existing
30-second timeout. The edit lock stays available while waiting. Queue head,
flags, guards and teardown deadline are checked again before launch; a changed
head or recent teardown discards the prepared attempt. The normal 90-second
queue cooldown and every fault halt remain intact.

The [policy](../experiments/own-xpu-runtime/ops/lane-queue/LATCH-POLICY.md)
records the remaining limitation: another lane can finish a teardown after
the last read, and a chain runner's internal windows never return through
this queue guard. Keep the other lane paused during chains of unfixed bundles.
Their own 90-second window gaps cover only their own teardowns. This is a queue
mitigation, not a repair or full serialization of the frozen wrappers.

## CPU verification

On `steve-b70s`, all **76 tests passed**, using fake clocks and temporary files:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/ops/lane-queue -v </dev/null
```

The 18 added cases cover recent/old/other-boot/undrained/missing/invalid state,
PAUSE/STOP/signal refusal, faults and latches during the wait, a newer shared
teardown, checks/logging that consume the remaining interval, the final guard
updating teardown or creating PAUSE, queue edits while waiting, and a bounded
timeout when teardown keeps moving. Existing queue tests now isolate teardown
and boot files in temporary directories; no test depends on live drain state.
Independent read-only review found no blockers.

Both live queues passed their read-only CPU plans, including packet seal
checks. No job was launched:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py plan --lane A </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py plan --lane B </dev/null
```

| Queue | Planned jobs | Result | SHA256 before and after planning |
| --- | --- | --- | --- |
| A | packet111r composite control/candidate/control; packet118 composite control/candidate/control | 6 passed, exit 0 | `9892b081775287f11ca714a2c0a3af7a7d825d85d04aea3cecca6b4a7d8b67b5` |
| B | packet118 smoke and composite control/candidate/control; packet116 micro 1/2; packet117 micro 1/2 | 8 passed, exit 0 | `5d41b13e416f0c5f339dfc422d2d1b01918b2d7b28eaba2664ede2b460d37a8d` |

AST comparison against committed source confirmed `validate`, `read_queue`,
`plan_job`, `command`, all of `Backend`, `report_failure_evidence`, and `main`
are unchanged. `git diff --check` passes.

The initial `git pull --rebase` refused because unrelated orchestration files
were dirty; `git fetch` confirmed HEAD and origin/main both at
`ed996c9126c999d51cad5446c7f325a968c6d690`. Other workers' changes were preserved.
No GPU, service, sudo, setting, live queue, event log, inflight record, PAUSE/STOP,
coordination marker or latch was changed by this work. The coordinator restarts
drivers between jobs to pick up the code; this task performed no restart.
