# Packet73 coordinator handoff

Preparation is CPU-only. Only the coordinator may run the following device
screens in its authorized lane unit after current fault review and admission.
The shared v3 drain, lane locks and coordination roots remain unchanged.
The private v4 wrapper stops its own ranks even if the teardown gate refuses,
and releases the lane after clean drain/postflight before CPU reporting.

## CPU checks

From the repository root:

```bash
p73=experiments/own-xpu-runtime/stage2/packet73-hc-experts2
nice -n 19 taskset -c 8-15,24-31 python3 -B "$p73/final_check.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$p73/screen/run.py" --lane A --jobs "$p73/screen/jobs-A.txt" --plan </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$p73/screen/run.py" --lane B --jobs "$p73/screen/jobs-B.txt" --plan </dev/null
```

B plan mode checks every possible candidate sandwich and labels its winner
pending. `best-of-lane-A` in the B job is symbolic, not a sixth mutable seal.
Execution resolves it from A's hash-checked, completed receipts.

## Device screens, prepared but not launched

The two proposed queue lines are:

- [`proposed-p73-A.txt`](../../ops/lane-queue/proposed-p73-A.txt)
- [`proposed-p73-B.txt`](../../ops/lane-queue/proposed-p73-B.txt)

Their argv invokes these commands inside the queue manager's already authorized
lane environment, substituting its current review file for `REVIEW_JSON`:

```bash
/usr/bin/python3 -B experiments/own-xpu-runtime/stage2/packet73-hc-experts2/screen/run.py \
  --lane A --jobs experiments/own-xpu-runtime/stage2/packet73-hc-experts2/screen/jobs-A.txt \
  --fault-review REVIEW_JSON --authorized-device-window </dev/null

/usr/bin/python3 -B experiments/own-xpu-runtime/stage2/packet73-hc-experts2/screen/run.py \
  --lane B --jobs experiments/own-xpu-runtime/stage2/packet73-hc-experts2/screen/jobs-B.txt \
  --fault-review REVIEW_JSON --authorized-device-window </dev/null
```

A: production → hc-wide → experts2-a → experts2-b → combined → production.
B, after A finishes: production → best exact improving candidate → production.
All six A screens must pass all 13 exact checks. The winner has the highest
class-balanced rate and must exceed the mean of the two production controls.
Ties follow A order. No improving candidate means B refuses before any launch;
there is no fallback candidate or retry. B also refuses incomplete or failed A
receipts. A result in one lane does not establish an improvement in the other.

Each screen is expected to take about 210 seconds. The 3,600-second watchdog
exceeds the required 840-second minimum; it is inherited unchanged. Gaps are
90 seconds: A about 28.5 minutes, B about 13.5 minutes, planning estimates only.
The runner never restarts a failed screen, creates a service or leaves a server
resident. Current ownership, device health, memory and unit checks still apply.

After both lanes, compare on CPU:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet73-hc-experts2/screen/compare.py </dev/null
```

The next measurement is the complete in-engine screen. No packet73 kernel
microbenchmark or interpolated bandwidth claim substitutes for it. Screens
use the incident64 plus fixed twelve cold 128-token requests, packet49 exact
oracle, cached_tokens=0 and 99/(t100−t1), median within class then across classes.
They remain diagnostic: strict 512-token qualification and any full record
chain or external submission are outside this preparation.
