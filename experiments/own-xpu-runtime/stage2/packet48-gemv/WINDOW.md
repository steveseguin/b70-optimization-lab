# Packet48 coordinator windows

Preparation does not run these commands. After releasing other GPU work, the
coordinator establishes current boot health and exclusive device ownership
under `docs/local-ops.md`. One physical Level Zero card, **index 0**, is used;
no visibility selector is admitted. The native program verifies PCI
**0000:23:00.0** before creating a context, and records its PCI address and
driver. This is the same unfiltered index convention as packet45/46, not Linux
DRM card0 (0000:43:00.0 on this boot). The host mapping was independently
recorded in coordinator commit `3ee379260`; no packet47 directory was read or
modified by this packet. Check the coordinator's physical mapping before admission.

Verify the CPU seal, then run E1, E2, T1 and T2 as separate, single-attempt
windows. Check the completed passing `window.json` and safe teardown before
each next command. Timing additionally validates the two exactness receipts
and their complete comparison bytes/hashes. No failure is retried automatically.
Use a fresh suffix instead of overwriting any output or unit name.

```bash
P48=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet48-gemv
P48_LIBS="${LD_LIBRARY_PATH:?supply installed oneAPI runtime libraries}"
P48_REVIEW="${REVIEWED_THROUGH_UTC:?supply coordinator-reviewed UTC boundary}"

systemd-run --user --unit=packet48-e1-p48-a --wait \
  --property=KillMode=process --property=SendSIGKILL=no --property=TimeoutStopSec=90s \
  /usr/bin/bash "$P48/coordinator-exact.sh" "$P48_LIBS" "$P48_REVIEW" "$P48/evidence/p48-a-e1"

systemd-run --user --unit=packet48-e2-p48-a --wait \
  --property=KillMode=process --property=SendSIGKILL=no --property=TimeoutStopSec=90s \
  /usr/bin/bash "$P48/coordinator-exact.sh" "$P48_LIBS" "$P48_REVIEW" "$P48/evidence/p48-a-e2"

systemd-run --user --unit=packet48-t1-p48-a --wait \
  --property=KillMode=process --property=SendSIGKILL=no --property=TimeoutStopSec=90s \
  /usr/bin/bash "$P48/coordinator-timing.sh" "$P48_LIBS" "$P48_REVIEW" "$P48/evidence/p48-a-t1" \
  "$P48/evidence/p48-a-e1/window.json" "$P48/evidence/p48-a-e2/window.json"

systemd-run --user --unit=packet48-t2-p48-a --wait \
  --property=KillMode=process --property=SendSIGKILL=no --property=TimeoutStopSec=90s \
  /usr/bin/bash "$P48/coordinator-timing.sh" "$P48_LIBS" "$P48_REVIEW" "$P48/evidence/p48-a-t2" \
  "$P48/evidence/p48-a-e1/window.json" "$P48/evidence/p48-a-e2/window.json"

nice -n 19 taskset -c 4-15,20-31 python3 -B "$P48/summarize.py" \
  --windows "$P48/evidence/p48-a-t1/window.json" "$P48/evidence/p48-a-t2/window.json" \
  --output "$P48/evidence/p48-a-summary.json"
```

`P48_REVIEW` is the actual UTC instant through which this boot's prior faults
were reviewed and required recovery completed, not a convenient current time.
Use exactly the same boundary in all four windows. The wrapper retains the
full boot journal, checks every line after that boundary, polls during the
child, and requires a five-second clean postflight. A new fault writes a boot
latch and invalidates the run. Current-boot recovery belongs to the coordinator.

The supervisor requests cooperative SIGTERM once, then allows a bounded drain.
Return 75 means an uncertain/live child is retained: inspect its recorded PID
and preserve evidence. Do not advance or hard-kill its process group. No
`RuntimeMaxSec`, default cgroup kill, restart policy, reset or reboot is allowed.

Admission requires the immutable CPU source/binary/gate seal, closed environment,
nice19/CPU4–15,20–31, 16 GiB MemAvailable, 8 GB remaining disk reserve and no
visible foreign Xe clients. The `/proc` check is passive; hidden foreign-user
clients remain the coordinator's responsibility. Synthetic weight generation,
repacking and uploads stay in memory; no model path is accepted. Largest
simultaneous weight banks are about 1.46 GB host and 1.46 GB device during the
IQ3 exception (two projections, old/new, all512 experts), plus small operands.
No cache, memory, swap or power setting changes occur.

Raw outputs: `run/receipt.json`, `comparisons.jsonl`, `iterations.jsonl`.
Every comparison includes input and output SHA256 plus exact extent; timing
rows retain every event start/end. `summary.json` separates a completed window
from meeting the speed bar and from control comparability. Both fresh owners
must meet the M1 bar. M2 and each route-overlap stratum remain separate reports.
No synthetic operator result is a full-model quality pass or a tokens/s claim.

CPU reproduction (serial, no device execution):

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P48/build.py" --kind gnu
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P48/build.py" --kind intel
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P48/build.py" --kind device
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P48/cpu_gates.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P48/python_gates.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P48/seal.py"
```

Compilation of the SYCL binary is CPU-only. Its first execution is E1.
Do not edit a sealed source or rebuild while coordinator windows are active.
