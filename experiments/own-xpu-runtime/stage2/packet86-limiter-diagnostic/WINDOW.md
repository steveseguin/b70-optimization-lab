# Packet86 coordinator handoff

**diagnostic_nonexact: true. CPU preparation did not launch a device or service.**

Primary proposal: [`proposed-p86-B.txt`](../../ops/lane-queue/proposed-p86-B.txt).
Equivalent lane A: [`proposed-p86-A.txt`](../../ops/lane-queue/proposed-p86-A.txt).
Both were planned on temporary queue copies. Neither was appended to a live
queue. The coordinator retains responsibility for current fault review,
authorization, lane reservation, unit limits, available memory and GPU work.

Each proposal has eight separate views, one load each, in this order:
production, exp-nodeq, exp-constgrid, exp-onecached, hc-nodeq, hc-constscale,
exp-loadkeep, hc-loadkeep. Each load runs one 64-token incident request and
12 control plus 12 instrumented 128-token requests. Sampling stays at generated
indices 9–16. The control arm disables observation only, not the selected ablation.
Device watchdog remains 3,600 seconds **per view**, with no retries or restarts.
The inherited approximately 420-second work estimate per view excludes loading,
drain, queue gaps and contention; eight loads are not promised to finish in an
hour. The brief's hour target applies to CPU preparation/sealing.

From the repository root, one CPU-only plan is:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet86-limiter-diagnostic/run_screen.py \
  --view exp-nodeq --lane B --plan \
  --output experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/packet86-B-a/exp-nodeq </dev/null
```

After all eight safely completed lane-B jobs, generate the comparison:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet86-limiter-diagnostic/report.py \
  --runs experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/packet86-B-a \
  --output experiments/own-xpu-runtime/stage2/packet86-limiter-diagnostic/evidence/limiter-B.json </dev/null
```

Use the equivalent A paths for A. Do not merge different lanes or binaries into
one comparison. A diagnostic result needs independent repeat/control work before
a mechanism is treated as stable. No screen result can become a speed headline.

An expected output mismatch produces a separate diagnostic outcome. Shared v4's
retained quality refusal is expected for such an arm; only the exact post-release
reporting refusal is accepted. A memory, protocol, device, drain or numerical
sticky failure remains a failure. Do not retry a failed arm automatically.
