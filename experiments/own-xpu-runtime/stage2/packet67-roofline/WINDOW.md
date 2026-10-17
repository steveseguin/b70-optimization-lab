# Packet67 coordinator windows

No GPU was used to prepare this packet. The coordinator owns device admission and runs these commands only in an authorized window. Existing packet64/65/66 work is protected. The copied wrapper retains packet65's shared crash-closed leases, lane device masks, memory admission, first-fault abort, one model lifetime, graceful drain, evidence binding and no retries.

Jobs: [lane A](screen/quick/jobs-A.txt), [lane B](screen/quick/jobs-B.txt). A: production, hc-a, hc-f, rec-head, combined, production. B reverses the four candidate views. Each screen is expected to take about 3.5 minutes; six screens and five 90-second gaps are about 29 minutes per lane, excluding admission/drain. Watchdog is 3,600 seconds per screen, exceeding four times the expected duration.

CPU verification and plan inspection (no model):

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet67-roofline
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/verify_packet.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/screen/quick/run.py" --lane A --jobs "$P/screen/quick/jobs-A.txt" --plan </dev/null
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/screen/quick/run.py" --lane B --jobs "$P/screen/quick/jobs-B.txt" --plan </dev/null
```

Coordinator launch, after setting the existing `P49_LDP` library path and `FAULT_REVIEW` evidence path in its environment. Do not print their contents. These are commands to run, not a record of device execution:

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet67-roofline
: "${P49_LDP:?coordinator must provide the existing runtime library path}"
: "${FAULT_REVIEW:?coordinator must provide the current fault review evidence path}"
systemd-run --user --unit=screen-p67-quick-A \
  --property=Restart=no --property=SendSIGKILL=no --property=KillMode=process \
  --property=ExitType=cgroup --property=TimeoutStopSec=infinity --property=Nice=0 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/taskset -c 0-3,16-19 /usr/bin/env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" \
  /usr/bin/python3 -B "$P/screen/quick/run.py" --lane A \
  --jobs "$P/screen/quick/jobs-A.txt" --fault-review "$FAULT_REVIEW" \
  --authorized-device-window </dev/null
systemd-run --user --unit=screen-p67-quick-B \
  --property=Restart=no --property=SendSIGKILL=no --property=KillMode=process \
  --property=ExitType=cgroup --property=TimeoutStopSec=infinity --property=Nice=0 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/taskset -c 4-7,20-23 /usr/bin/env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" \
  /usr/bin/python3 -B "$P/screen/quick/run.py" --lane B \
  --jobs "$P/screen/quick/jobs-B.txt" --fault-review "$FAULT_REVIEW" \
  --authorized-device-window </dev/null
```

After both lanes finish:

```bash
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/screen/quick/compare.py" </dev/null
```

The helper checks every token against packet49, 13 checks including incident64, cold requests, identities and drain proofs. It recomputes 99/(t100−t1), median within class then across classes, and compares against the mean of that lane's two production controls. Never combine lane A's control with lane B's candidate. No failed job is automatically retried. Device quality and speed are pending; any promotion needs the full registered quality/repeat/fresh-process and 512-token suite gates.
