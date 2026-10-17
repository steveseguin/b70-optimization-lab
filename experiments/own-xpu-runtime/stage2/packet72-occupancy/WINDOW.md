# Coordinator handoff

No device work was run during packet72 preparation. The coordinator installs
the proposed JSON lines into the live queues after review; this packet never
edits those queues or starts a unit.

1. [LaneA proposal](../../ops/lane-queue/proposed-p72-A.txt): production →
   attention-out → combined → production. Four fresh screens, one model load
   each, expected about3.5 minutes each plus three90-second gaps.
2. Only after laneA succeeds,
   [laneB proposal](../../ops/lane-queue/proposed-p72-B.txt): production →
   attention-out → production. Three fresh screens plus two90-second gaps.
   The runner independently verifies laneA receipts before starting any screen.
   It refuses an incomplete, inexact or non-improving candidate.

`combined` equals attention-out: the bandwidth rule admitted only this one new
class. The laneA decision averages both aliases and compares them with the
mean of both production controls. LaneB never tests another candidate or
searches for a lucky alias. Both lanes keep the thirteen exact checks,
unchanged packet49 oracle, full16-bit KV, fixed cold prompts and fault guards.

The screen watchdog is3600 seconds (over4×210 seconds). Shared drains remain
60 seconds apart and internal screen gaps are90 seconds. The v4 private copy
releases the cooperative and legacy lane leases after drain and postflight,
before CPU reporting. No automatic retry, recovery or server restoration.

The queue format and unit ownership rules remain those in
[lane-queue README](../../ops/lane-queue/README.md).

To reproduce the CPU queue checks from the repository root:

```sh
P=experiments/own-xpu-runtime/stage2/packet72-occupancy
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/queue_plan.py" </dev/null
```

This runs `lanequeue.py plan` in the packet's private `queue-plan/` directory,
using exact copies of the proposals. It does not create fault-review receipts,
read the journal, start units or change live queue files.
[Validation receipt](evidence/queue-plans.json).

After both lanes finish, `screen/compare.py` validates and compares their
receipts on CPU. A passing screen remains diagnostic; a new record needs the
full unchanged-target chain. No performance improvement is claimed here.
