# Coordinator handoff

Use the shared, hash-pinned `stage2/screen/v4-lanes` unchanged. No proposed job
has been added to a live queue. Choose ONE first lane; do not schedule both grids:

| First free lane | Full grid proposal | Other-lane confirmation proposal |
| --- | --- | --- |
| A | [proposed-p83-A-grid.txt](../../ops/lane-queue/proposed-p83-A-grid.txt) | [proposed-p83-B-confirm.txt](../../ops/lane-queue/proposed-p83-B-confirm.txt) |
| B | [proposed-p83-B-grid.txt](../../ops/lane-queue/proposed-p83-B-grid.txt) | [proposed-p83-A-confirm.txt](../../ops/lane-queue/proposed-p83-A-confirm.txt) |

The grid is production, Q4/g32, prefix99.0, prefix98.5, production. The other
lane recomputes the exact best candidate from the completed first-lane artifacts
and runs production, winner, production. Every grid screen must match packet49
on all twelve requests and the incident check. A candidate must beat both first-lane
controls. If none does, confirmation refuses; there is no fallback candidate or retry.
The two lanes may have different absolute speeds; compare each only with its own
controls. Two-lane evidence is screening, not a headline or completed quality chain.

Plans run on CPU:

```sh
P=experiments/own-xpu-runtime/stage2/packet83-draft-bytes
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/final_check.py" </dev/null
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/queue_plan.py" </dev/null
```

The four proposed JSON job lines use the coordinator's existing review, fault,
lane lease, fresh output, 90-second gaps, startup and graceful teardown rules.
CPU preparation grants no device authorization. `--mode grid --lane A|B` selects
a grid; `--mode confirm --lane B --source-lane A` (or the reverse) is winner-gated.
The queue supplies `--fault-review {REVIEW} --authorized-device-window`.
Expected grid duration is about25minutes (five loads/screens plus four90-second
gaps); confirmation about15minutes. These are planning estimates; admission waits
are additional. Shared per-screen watchdogs and cleanup are unchanged.

Outputs are fresh shared-wrapper paths `screen/v4-lanes/evidence/p83-<lane>-<mode>-<index>-<choice>`.
Each screen keeps the standard sealed summary with request hit/guess counts.
The packet runner validates and prints each request's acceptance, mean request
acceptance, pooled hits/guesses acceptance, exactness and class-median rate after
shared cleanup and release. Preserve the queue log alongside the screen evidence.
Do not infer acceptance from the independent-text coverage table.
