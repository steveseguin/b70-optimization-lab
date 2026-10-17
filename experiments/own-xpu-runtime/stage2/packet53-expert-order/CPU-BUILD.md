# CPU preparation commands

Run serially; never invoke a device binary during preparation. All commands
use nice19, permitted cores and Python-B. The build helper takes a packet-local
exclusive lock, checks the1GB build cap and leaves at least18GB root free at
admission. CPU gates force OMP_THREAD_LIMIT=1 despite the inherited control's
two-thread pragma. Existing packet45 support objects are hash-verified and
relinked against their sealed baseline before reuse; Intel host tests cover
new source under Intel, with historical GNU host support reused explicitly.

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet53-expert-order
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind host
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind intel-host
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind device
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/cpu_gate.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/python_gate.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/cleanup.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/seal.py"
```

The device step compiles/links only. The proof compares decoded values, raw
FP32 chains/trees, BF16 outputs, assignment coverage and route/error controls.
Two full-shape host repetitions each include all60 M1/M2 control/candidate
comparisons. Final review/docs precede the last Python gate and seal; changing
any sealed source invalidates it. Retain failures, never silently discard them.

The CPU gate also compiles one standalone GNU AddressSanitizer/UBSan proof
from the checked host mirror, runs it once at one thread, and requires the
same check count/output hash as the four normal proof owners. Its source,
command, log and binary are included in the CPU receipt and final seal.
