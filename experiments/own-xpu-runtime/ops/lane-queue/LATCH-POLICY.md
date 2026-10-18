# Queue latch policy — 2026-10-18

## Compiler turns and device-time reviews

**New briefs use `experiments/own-xpu-runtime/ops/compile_turn.py`.** Packet94's
copy and other sealed packet copies stay frozen. A future build can put the
repository's `experiments/own-xpu-runtime/ops` directory first on `sys.path`
before importing `compile_turn.turn`; do not accidentally import its local
historical copy. The build still supplies `build_engine.limits()`.

The ops gate keeps the shared `/tmp/own-xpu-runtime-cpu-compile.lock`, foreign
compiler/build-tool checks, ten-second polling, one-hour blocker deadline and
the caller's safety limits. As before, acquiring the shared flock itself waits
without a separate deadline. It never signals a process or changes coordination.

`hold-lane-B` is written **before** A waits for B. While B's active marker
remains and A has no device descendant, that is admission waiting and compiles
may proceed. Once B's marker is gone, the hold blocks compiles, including
preflight and drain. A device child of the reservation owner also blocks even
if B's marker is still present. PID/start-tick ancestry keeps B's device child
from being mistaken for A's. Malformed/unreadable holds stay conservative;
the whole-host A marker also protects the short marker/hold release transition.
This is an observation before compilation, not an atomic reservation shared
with device launch: an already-running compile is never interrupted, and a
window can change after the check. Coordinator scheduling still matters.

`ops/gpu_time_review.py --hours N` retains its CLI and report sections. Service
lifetimes and queue START/DONE events are attribution only. Busy time comes
from live `own-rt-iq3` device children and current-boot device receipts, with
rank overlaps unioned. Whole-host credit on B requires that same device
evidence. The new `idle_admission_wait` category counts reservation waiting as
idle on the requesting lane, after subtracting any evidenced device activity.
No admission wait, cooldown or wrapper/report tail becomes busy time.

Some historical receipts have no exact child exit clock. The review uses
observed device/request intervals as a lower bound, discloses missing clocks,
and does not substitute drain completion or file modification times. Gaps with
no attributed device evidence are not proof that unrecorded work never ran.
The [work note](../../../../notes/2026-10-18-own-runtime-ops-monitor-compile.md)
records the 13:37–14:03 regression and CPU checks.

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/ops -p 'test_*.py' -v < /dev/null
```

## Queue fault boundaries

The queue checks the complete current-boot kernel journal **before** deciding
whether a screen latch belongs to this lane. It uses the `FAULT` and `DELETED`
expressions from `stage1/packet4-prep/driver/window_driver.py`. The existing
reviewed boundary stays fixed: boot prefix `2cba7160`, exactly two fault lines.
This agrees with the frozen fault-review helper's required count. Restarting a
driver never adopts a higher count. Postflight also compares with the recorded
job-start count.

When that check passes, `stage2/screen/v3/fault-<boot UUID>-A.json` stops A's
queue driver only; the B form stops B only. The UUID must have the reviewed
boot prefix and the exact lowercase UUID shape written by the v4 wrapper.
The filename owns the lane; the wrapper does not put a lane field in its JSON.

A third fault line, an unreadable journal/count, or a different boot blocks
both drivers. Lane-less, malformed, unknown-lane and other-boot latch names
remain global. Latches are never deleted, rewritten or archived by the queue.
Own-lane dead/live/unknown owner guards, wrapper teardown checks, PAUSE/STOP,
inflight records, failed-job recovery, and cooldown rules are unchanged. Live
cross-lane conflicts now wait before launch as described below.

This supersedes the queue README's statements that *every* other-lane latch
blocks queue preflight/postflight. It changes only queue admission. Frozen
wrappers retain their own guards: v4's `screen_main()` still refuses any
current-boot v3 latch, including another lane's. Passing this queue guard is
therefore not proof a frozen screen will launch; any required recovery remains
the coordinator's reviewed action. No wrapper bypass is installed.

The coordinator restarts drivers between jobs to pick up this code. Preparing
this change starts/stops no services and changes no live queue or latch.

## Live window overlap

Before launch, A waits while `active-lane-B.json` has a live owner, including
before B writes its teardown record and after drain until B releases its
reservation. A also waits for any live owner of a current-boot undrained
`screen/v3/teardown-state.json`. The frozen v4
`drain_gate.py::_screen_teardown_admit_locked` refuses **every** undrained
current-boot record for A, regardless of the owner's lane.

B retains the wrapper's one permitted overlap: the drain's `chain_reservation`
must equal `active-lane-A.json`, name lane A with scope `lane-A`, belong to the
current boot, and have matching live PID/start ticks. B waits on other live
undrained owners, including whole-host A reservations and pid-only v3 drains.
The wrapper still verifies B's own reservation and all three held locks;
the queue never grants an admission exception or acquires coordination locks.

Liveness uses `/proc/<pid>/stat`, matching the wrapper's handling of process
names, zombies and exited processes. Saved start ticks are checked when
available; pid-only records can establish only that the PID is live. Missing,
malformed, unreadable, dead or reused owners keep the existing guard/wrapper
path. Nothing repairs, removes or retries their records.

`WAIT-OTHER-LANE-LIVE` logs the job, owner PID, source file and monotonic
deadline, once per changed blocker. The live wait has a fixed **1800-second**
budget per preparation attempt, then refuses without launch/inflight state.
Every poll honors PAUSE/STOP/signals and checks the existing fault, marker and
latch guards. Sleeps are capped at one second and clamped nonnegative. The
edit lock stays available. A live conflict that appears during drain spacing
also waits; after it clears, the latest completed drain still needs the full
61-second spacing with its separate 120-second budget. The final launch check
rereads live ownership, flags and spacing after guards and queue-head checks.

This is an observation-based queue guard, not atomic cross-lane serialization:
a new window can still appear after the last read. Frozen wrappers remain the
final authority, and internal chain windows still bypass the queue. The
[overlap work note](../../../../notes/2026-10-18-own-runtime-ops-lane-overlap.md)
records the refusal and CPU verification.

## Shared teardown spacing

Immediately before a queued job, the driver reads
`stage2/screen/v3/teardown-state.json`. A readable record with the exact current
boot UUID, `drained: true`, and a finite nonnegative `completed_monotonic`
delays launch until that completion time plus **61 seconds** on
`CLOCK_MONOTONIC`. Old or other-boot records add no delay. Missing, unreadable,
invalid or undrained state adds no completed-drain delay; the live-window wait
above applies independently. Neither helper bypasses the journal, marker,
latch or frozen-wrapper guards.

The wait rereads the shared record and checks all existing queue guards on
each poll. It logs `WAIT-DRAIN-SPACING` with `wait_seconds` and the monotonic
deadline when first waiting or when that deadline changes. Sleeps are at most
one second and clamped to zero after checks/logging. Spacing has a 120-second
budget, renewed while waiting on a live conflict; if a still-pending spacing
deadline outlasts that budget, the driver refuses
without launching or creating an inflight record. Journal checks retain their
existing 30-second subprocess timeout. PAUSE/STOP and signal requests prevent
launch, and queue edits remain available while waiting. The queue head, flags,
guards and latest deadline are checked again before recording the launch.
The separate 90-second gap after a queue job remains unchanged.

This avoids entering the frozen wrappers' faulty 60-second sleep loop when
the last observed shared drain is recent. It does **not** fix their code or
serialize teardown writers with launch: a different lane can still complete
a new teardown after the final read. A chain runner's own windows do not pass
through the queue between launches. **Keep the other lane paused during chains
of unfixed bundles.** Their own 90-second window gaps suffice only without a
new cross-lane teardown. See the
[packet103 race note](../../../../notes/2026-10-18-own-runtime-packet103-chain-a-ws-drain-race.md)
and the [spacing change note](../../../../notes/2026-10-18-own-runtime-ops-drain-spacing.md).

CPU regression checks:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/ops/lane-queue -v < /dev/null
```

## Drain-fix check before chain readiness

Every new bundle's CPU preparation must run this command from the repository
root and retain its result before declaring any chain ready:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B scripts/check_drain_fix.py \
  experiments/own-xpu-runtime/stage2/<packet> < /dev/null
```

It must exit zero. The check reads every `drain_gate.py` and other files with
the cooldown sleep pattern, including nested copies. Every recognized sleep
must have a nonnegative argument, such as
`max(0.0, min(.25, until - self.now()))`. Unknown forms fail closed; comments
and quoted examples in Python do not count as executable sleeps. This is a
static check of that race, not a general runtime or chain-readiness certificate.

An `UNFIXED` copy blocks new-bundle chain readiness. Frozen bundles stay
unchanged; **bundles that fail need the other lane paused throughout their
chains**, including internal window transitions. The queue's 61-second spacing
alone does not protect those transitions. This policy does not change queues
or pause markers automatically.

The read-only [all-packet report](../drain-fix-report.json) records FIXED/UNFIXED
per path, source hashes and sleep line numbers. Regenerate it with
`scripts/check_drain_fix.py --all --json` under the same CPU restrictions;
exit one is expected while historical unfixed copies remain. Exit two means
an invalid/empty scan or a scan error, never a pass.
