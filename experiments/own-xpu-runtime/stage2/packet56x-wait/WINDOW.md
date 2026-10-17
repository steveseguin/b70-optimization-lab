# Coordinator screens: packet56x

Use screen v1 below, or v3 after its independent validation. GPU windows belong
to the coordinator; preparation used only CPU `--plan`. Run each arm once in
its own admitted `screen-*` systemd user unit, with the coordinator's approved
library path and actual reviewed fault boundary. Both arms retain packet56w's
rank-0 profiling property. Match CPU placement and priority to the control.
Do not run arms together or reuse an output directory.

(a) PAUSE polling until complete/deadline, yielding every 256 iterations:

```bash
P=experiments/own-xpu-runtime/stage2/packet56x-wait
nice -n 19 taskset -c 8-15,24-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B experiments/own-xpu-runtime/stage2/screen/screen.py \
  --profile tp2 --lineage "$P" --seal "$P/screen-seal-spin.json" \
  --binary "$P/build/device/own-rt-iq3" \
  --authorized-device-window --faults-reviewed-through "$REVIEWED_THROUGH" \
  --output experiments/own-xpu-runtime/stage2/screen/evidence/packet56x-spin-a
```

(b) 250 microsecond spin, then 20 microsecond sleep polling:

```bash
P=experiments/own-xpu-runtime/stage2/packet56x-wait
nice -n 19 taskset -c 8-15,24-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B experiments/own-xpu-runtime/stage2/screen/screen.py \
  --profile tp2 --lineage "$P" --seal "$P/screen-seal-sleep20.json" \
  --binary "$P/build/device/own-rt-iq3-sleep20" \
  --authorized-device-window --faults-reviewed-through "$REVIEWED_THROUGH" \
  --output experiments/own-xpu-runtime/stage2/screen/evidence/packet56x-sleep20-a
```

Append `--plan` for CPU-only admission checks. The saved plans use the epoch
only as a required parser argument; they authorize no fault waiver or device
work. `seal_and_plan.py` creates both seals and those saved plans. Never rerun
it over an existing seal. The two seals bind different executable hashes; a
binary from the other arm is rejected. No environment switch chooses a policy.

The screen checks the 64-token incident and all twelve 128-token prompts against
the unchanged packet49 oracle. It is diagnostic; GPU exactness, speed and full
qualification remain pending. Keep the ordinary screen admission, fault handling,
no-retry and graceful teardown rules. No record or submission is made here.
