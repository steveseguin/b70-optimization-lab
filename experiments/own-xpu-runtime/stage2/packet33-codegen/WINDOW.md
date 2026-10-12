# Coordinator windows — prepared, never executed here

Both commands below access a GPU and are **for the coordinator's separately
authorized window only**. Packet33 preparation was CPU-only. The binaries and
sources must match `build-receipt.json`; K2 requires successful K0 on the same
boot/card/binary/environment. A fresh output directory is mandatory. The wrapper
creates its HOME/TMPDIR below this packet. The native environment is closed:
HOME, PATH, LANG, LC_ALL, LC_CTYPE, OMP_NUM_THREADS, LD_LIBRARY_PATH, TMPDIR only.
No hidden SYCL/UR/IGC tuning variables are accepted.

From the repository root, with card2 available:

```bash
nice -n 19 ionice -c 3 env -i HOME=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet33-codegen/build/native-home TMPDIR=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet33-codegen/build/native-tmp PATH=/usr/bin:/bin LANG=C.UTF-8 OMP_NUM_THREADS=2 LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.0/lib python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/window.py --authorized-device-window --window K0 --card 2 --output experiments/own-xpu-runtime/stage2/packet33-codegen/build/k0-card2
nice -n 19 ionice -c 3 env -i HOME=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet33-codegen/build/native-home TMPDIR=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet33-codegen/build/native-tmp PATH=/usr/bin:/bin LANG=C.UTF-8 OMP_NUM_THREADS=2 LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.0/lib python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/window.py --authorized-device-window --window K2 --card 2 --output experiments/own-xpu-runtime/stage2/packet33-codegen/build/k2-card2 --k0 experiments/own-xpu-runtime/stage2/packet33-codegen/build/k0-card2/window.json
```

Run the long window in the coordinator's existing systemd user job protocol;
do not leave it attached to an agent shell. Change both output names together
for a later authorized attempt, never overwrite evidence. No automatic retries.

K0 uses the unchanged packet29 compile-smoke main linked with all candidate
images. It creates a device/context and builds images but submits no kernel.
K2 checks bytes, then measures200 repetitions of each declared arm. Payloads
above8,000,000bytes use eight distinct full-size weight/output banks and keep
pre/post equality outside timed events. Reread measurements for those payloads
are diagnostic and excluded by the aggregator. Full-size paired weights are
kept; no toy down replacement enters the table. Captures are compile-time
checked<=1024bytes and return-type warnings are errors.

Preflight: hash seal, K0 identity for K2, `ldd` with no missing libraries,
readable kernel journal cursor. Journal fault signatures are polled during the
child. A fault, coordinator signal, or watchdog sends SIGTERM once. Candidate
kernels finish and the native main reports failure before orderly teardown.
If draining has not finished after360seconds, the wrapper retains the PID and
returns failure; it never hard-kills, resets or reboots. The coordinator must
handle any retained process and follow host recovery rules. K0's unchanged
smoke main has no custom drain handler, but it submits no GPU kernel.

Expected durations only: K0~60seconds, K2~180seconds. Watchdogs300/720seconds
are>=4times expectations and>=300seconds. Expectations are not measurements.
All failures are retained and make admission false. `summary.json` and
`dispatch-measured.json` appear only after a complete valid K2. Native output,
events, byte receipts, journal segments, hashes and ldd output stay in the new
window directory. No model server is started by either window.
