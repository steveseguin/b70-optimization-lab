# Queue latch policy — 2026-10-18

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
Dead/live/unknown owner markers, wrapper teardown checks, PAUSE/STOP, inflight records,
failed-job recovery, and cooldown rules are unchanged.

This supersedes the queue README's statements that *every* other-lane latch
blocks queue preflight/postflight. It changes only queue admission. Frozen
wrappers retain their own guards: v4's `screen_main()` still refuses any
current-boot v3 latch, including another lane's. Passing this queue guard is
therefore not proof a frozen screen will launch; any required recovery remains
the coordinator's reviewed action. No wrapper bypass is installed.

The coordinator restarts drivers between jobs to pick up this code. Preparing
this change starts/stops no services and changes no live queue or latch.

## Shared teardown spacing

Immediately before a queued job, the driver reads
`stage2/screen/v3/teardown-state.json`. A readable record with the exact current
boot UUID, `drained: true`, and a finite nonnegative `completed_monotonic`
delays launch until that completion time plus **61 seconds** on
`CLOCK_MONOTONIC`. Old or other-boot records add no delay. Missing, unreadable,
invalid or undrained state keeps the existing admission path; it never bypasses
the journal, marker, latch or frozen-wrapper guards.

The wait rereads the shared record and checks all existing queue guards on
each poll. It logs `WAIT-DRAIN-SPACING` with `wait_seconds` and the monotonic
deadline when first waiting or when that deadline changes. Sleeps are at most
one second and clamped to zero after checks/logging. Each wait has a 120-second
budget; if a still-pending deadline outlasts that budget, the driver refuses
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
