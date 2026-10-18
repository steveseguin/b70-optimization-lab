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
Dead/live/unknown owner markers, teardown checks, PAUSE/STOP, inflight records,
failed-job recovery, and cooldown rules are unchanged.

This supersedes the queue README's statements that *every* other-lane latch
blocks queue preflight/postflight. It changes only queue admission. Frozen
wrappers retain their own guards: v4's `screen_main()` still refuses any
current-boot v3 latch, including another lane's. Passing this queue guard is
therefore not proof a frozen screen will launch; any required recovery remains
the coordinator's reviewed action. No wrapper bypass is installed.

The coordinator restarts drivers between jobs to pick up this code. Preparing
this change starts/stops no services and changes no live queue or latch.

CPU regression checks:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/ops/lane-queue -v < /dev/null
```
