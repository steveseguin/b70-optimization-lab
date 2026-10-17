# Coordinator screens

Four immutable views under `selections/` share one compiled device binary.
The private `screen/` starts as a copy of frozen `stage2/screen/v4-lanes/`.
It retains all 13 packet49 exact requests, one model lifetime per screen,
lane leases, device masking, stop/fault checks,90-second gaps, shared drains,
and release before CPU reporting. No live queue was changed.

Lane A: production → head-packed → dense-packed → combined → production.
Every screen must pass all 13 checks. Choose the highest class-balanced rate
among the three candidates only if it beats BOTH production controls.
Ties choose the earlier candidate in that fixed order. No winner means no
lane-B launch. Lane B: production → that exact winner → production.
`screen/best.py` verifies the complete hash-bound lane-A receipts before it
selects one of the three immutable B job files. It does not edit or reseal a
view. Both lane-B controls and its candidate must pass before considering a
later full-chain qualification.

Prepared proposals (do not confuse these with live queues):

- `ops/lane-queue/proposed-p74-A.txt`
- `ops/lane-queue/proposed-p74-B.txt`

The proposals pass `lanequeue.py plan` against a private temporary queue copy
under this packet's `queue-plan/`. The A plan checks five screens; the B plan
checks all three possible sandwiches (nine plans), while execution selects
only one sandwich. Both proposals remain coordinator-owned.

CPU verification from repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet74-packed-dense/final_check.py </dev/null
```

For the optional synthetic operator run, use [MICROBENCH](MICROBENCH.md).
Screens use128-token answers and are diagnostic, with the unchanged13 exact
checks. They do not satisfy the strict 512-token final performance gate or
replace full-chain deterministic/fresh-server quality evidence. Do not submit
or promote a screen result.
