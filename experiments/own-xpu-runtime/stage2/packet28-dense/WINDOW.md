# Prepared coordinator windows

Preparation ran CPU programs and compilers only. These device commands were not run.
The coordinator must establish card ownership and current host health before using
this packet; historical permissions are not a new GPU admission. Both windows take
`--card N`. A fresh output directory is required; no automatic retry exists.

From `/home/steve/llm-optimizations`, after rebuilding and sealing if source changed (recorded family CPU compile commands
are in dense-cpu-receipt.json and expert-build-receipt.json):

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet28-dense/build.py host
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet28-dense/build.py icpx-host
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet28-dense/build.py device
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet28-dense/test_protocol.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet28-dense/finalize_cpu.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet28-dense/build.py seal
```

The launch environment is intentionally explicit. Shell/device selector variables
must not slip into the native process. Substitute another admitted card for0 if needed.
Use the actual HOME from the shell; do not repurpose it.

K0 builds every linked device kernel without submitting a model/kernel execution:

```bash
nice -n 19 ionice -c 3 env -i HOME="$HOME" PATH=/usr/bin:/bin LANG=C.UTF-8 OMP_NUM_THREADS=2 XDG_RUNTIME_DIR="/run/user/$(id -u)" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus" python3 -B experiments/own-xpu-runtime/stage2/packet28-dense/window.py --authorized-device-window --window K0 --card 0 --output experiments/own-xpu-runtime/stage2/packet28-dense/build/k0-card0
```

G2 runs current then candidates, byte gates,200 timed repetitions, and two fresh owners:

```bash
nice -n 19 ionice -c 3 env -i HOME="$HOME" PATH=/usr/bin:/bin LANG=C.UTF-8 OMP_NUM_THREADS=2 XDG_RUNTIME_DIR="/run/user/$(id -u)" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus" python3 -B experiments/own-xpu-runtime/stage2/packet28-dense/window.py --authorized-device-window --window G2 --card 0 --k0 experiments/own-xpu-runtime/stage2/packet28-dense/build/k0-card0/window.json --output experiments/own-xpu-runtime/stage2/packet28-dense/build/g2-card0
```

Expected K0/G2 duration:47s/434s; enforced watchdogs300s/1736s. See DEADLINES.md.
Timing uses GPU event timestamps, not CPU mock time. All resident fixture uploads and
verification copies are outside the200-launch loops. Candidate failures are reported
before teardown and the remaining candidates continue. The measured dispatch file is
created only from completed two-owner evidence, never from the planning hypotheses.
