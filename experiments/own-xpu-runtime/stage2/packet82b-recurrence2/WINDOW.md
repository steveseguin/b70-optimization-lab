# Packet82b shared-v4 screen proposals

Preparation is CPU only. The shared pinned wrapper at `../screen/v4-lanes`
owns device admission, masking, one model lifetime, exact packet49 oracle
checks, drain/health evidence and teardown. Do not edit or copy that wrapper.
No device screen has been run for packet82b by this preparation.

New proposals in `../../ops/lane-queue/`:

| File | Registered work |
| --- | --- |
| proposed-p82b-A-grid.txt | Full production / rec-both / rec-both-plus / production grid on A. |
| proposed-p82b-B-grid.txt | Same full grid on B. |
| proposed-p82b-A-confirm.txt | Control / eligible B winner / control on A. |
| proposed-p82b-B-confirm.txt | Control / eligible A winner / control on B. |

The coordinator chooses the starting grid and confirms its winner on the other
lane. Both full-grid files exist as requested; their existence does not require
duplicate grids. No live queue was appended or altered. `queue_plan.py` copies
each proposal to a temporary `queue-A.txt` or `queue-B.txt` and invokes the
unchanged queue planner there.

Every screen binds its own selection and placement audit, uses the same new
binary and dispatch, and retains packet84's wide-HC/ordered composition.
Placement 1 is draft rank 1, target 24/24. No alternate experts, routing, norms,
draft head, state precision or prefix policy is introduced.

The grid's `rec-both` is an exact kernel alias and a third null control.
Only `rec-both-plus` is eligible for confirmation; it must beat every control,
including the alias. Any inexact or incomplete screen refuses selection.
Confirmation reads the opposite lane's sealed, finished results at execution
time; planning cannot claim there is already a winner. Each run uses a fresh
output directory, 90-second gaps and no automatic retry.

CPU planning commands (prefix with nice 19 and CPUs 8–15/24–31; stdin `/dev/null`):

```sh
python3 -B run_screens.py --lane A --mode grid --plan
python3 -B run_screens.py --lane B --mode grid --plan
python3 -B run_screens.py --lane A --mode confirm --source-lane B --plan
python3 -B run_screens.py --lane B --mode confirm --source-lane A --plan
```

The screen has twelve cold 128-token requests plus the 64-token incident check.
Rates are the median across prompt-class medians over 99 inter-token intervals.
Draft acceptance is retained per request and pooled. This is diagnostic
screening: no headline, record chain or external submission follows from a
CPU pass or this shorter suite alone. A later device run must first establish
actual byte/oracle parity, guard behavior and performance.
