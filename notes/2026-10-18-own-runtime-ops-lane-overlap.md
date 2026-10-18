# Queue admission while another lane is live — 2026-10-18

Lane A now waits before launching into a live lane-B window, then observes
the existing 61 seconds after the shared drain. B can still overlap a live A
exactness window under the frozen wrapper's existing rules. Only
[lanequeue.py](../experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py)
changes operational behavior; no frozen wrapper changed.

## Incident and admission rule

The task reports B's `packet122-micro-B-1` starting at 11:24:02 UTC, then
`p118-89f2d60778eb2d6e-composite-A-2-control` starting at 11:24:41 and refusing
in six seconds. Its shared teardown was still undrained. The refusal left
an A owner marker and stopped that queue driver. The completed-drain spacing
guard from `b83172aa0` did not cover a live window.

The exact rule is in
[v4 drain admission](../experiments/own-xpu-runtime/stage2/screen/v4-lanes/drain_gate.py),
`_screen_teardown_admit_locked`: a current-boot undrained record refuses A
unconditionally. B's exception requires the recorded `chain_reservation` to
equal `active-lane-A.json`, with lane A, scope `lane-A`, current boot and live
matching PID/start ticks. The wrapper additionally verifies its own B
reservation and that the teardown and both lane locks are held.

The queue now waits for a live B marker before an A launch, even during the
reservation's pre-drain or post-drain phases. For any live current-boot
undrained owner it waits unless the arriving lane is B and the A reservation
matches the exception above. Thus a whole-host A owner, an unregistered live
owner or another B drain cannot accidentally use the B-over-A exception.
Own-lane markers still stop at the existing guard before this helper runs.

Process checks read `/proc/<pid>/stat`, handle spaces/parentheses in names,
reject zombies/exited processes and match saved start ticks where present.
Pid-only v3 records cannot prove more than PID liveness. Dead, reused,
unreadable or malformed owners remain on the old guard/wrapper path: this is
neither recovery nor permission to bypass a refusal.

## Wait and remaining boundaries

`WAIT-OTHER-LANE-LIVE` records each changed blocker with job name, owner PID,
source and monotonic deadline. The live wait is bounded at 1800 seconds per
preparation attempt. Every poll retains PAUSE/STOP/signals, fault count,
own-marker and latch guards. Sleeps are at most one second and clamped after
logging. No queue edit lock is held while waiting. A timeout refuses before
creating inflight state or launching anything.

The existing 120-second completed-drain wait budget is renewed while a live
conflict remains. Once it clears, the latest completed drain must still be at
least 61 seconds old. Live ownership is checked during spacing and again
after the final guards and queue-head check. The normal 90-second inter-job
gap remains unchanged.

This does not atomically serialize launch with the other lane: a new window
can begin after the last observation. The frozen wrapper remains the final
authority. Internal chain windows bypass this queue check; keep the other
lane paused during chains with unfixed cooldown loops, as recorded in
[LATCH-POLICY.md](../experiments/own-xpu-runtime/ops/lane-queue/LATCH-POLICY.md).
The queue never acquires coordination locks, rewrites markers or retries a
failed arm.

## CPU verification

All **96 tests passed** on `steve-b70s`, including 20 new cases using fake
files, process stat records, backends and clocks:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/ops/lane-queue -q </dev/null
```

Coverage includes an A wait longer than the old spacing budget and a start
exactly 61 seconds after B drains; undrained owner without marker; pid-only
v3 records; marker-only pre/post-drain phases; B's permitted A overlap;
other refused live combinations; PAUSE/STOP/signals; fault/latch interruption;
dead/reused/zombie owners; invalid/other-boot state; bounded timeout; slow
logging; queue edits; and a B window appearing during spacing or the final
launch guard. All prior fault, latch, recovery and spacing tests pass.

Both live queues were planned read-only using:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py plan --lane A </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py plan --lane B </dev/null
```

| Initial live plan | Result | Queue SHA256 before and after that plan |
| --- | --- | --- |
| A: remaining packet118 composite control | Exit 1: existing screen evidence output | `45823bd44613c7dec5d36566bfc00c84a45974aba44563152b557b1eb655346f` |
| B: packet122 HC micros 1/2, packet120 B 0/1/2 | Five passed, exit 0 | `4612eca779d258ce412ff0653d8c61833ade0cdfb6e15e4fd6a2cda2936bc5f0` |

The A plan's nested diagnostic is `ValueError: new screen evidence output
required`. Running the committed driver source's plan entrypoint read-only
confirmed the same A failure. During the baseline B comparison, the first
micro's output became occupied by ongoing coordinator work, so it failed
fresh-output planning while the other four passed. The queue bytes still
matched before/after that baseline plan. Later the coordinator removed that
completed entry; all four remaining B entries passed the new driver's plan,
exit zero. These are live-state changes, not a planning-code change;
no queue or output was repaired to make a plan pass.

AST comparison against the committed source confirms `Backend` (all fault,
marker and latch guards), `command`, `validate`, `read_queue`, `plan_job`,
`report_failure_evidence`, `main`, and `drain_spacing_deadline` are unchanged.
`git diff --check` passes.

## Repository and handoff

`git pull --rebase` refused the unrelated dirty orchestration files.
`git fetch` confirmed main's HEAD and origin/main both at
`b977c14647fdbc4283bb4fcad314b8d15a23b6d1`. Those files were preserved.
No GPU, service, sudo, setting, live queue, event log, inflight record,
PAUSE/STOP, coordination marker or latch was changed by this work. The
coordinator picks up the code on its normal between-job driver restart;
this task performed no restart and does not recover the refused A arm.
