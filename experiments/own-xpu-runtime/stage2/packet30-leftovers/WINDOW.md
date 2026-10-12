# Prepared coordinator window: not run here

CPU preparation did not execute a device binary, query Level Zero, or open a DRM
node. A coordinator with a separately admitted idle card owns these commands.
They build kernels first (K0); G3 then runs two fresh processes, exactness and200
repetitions per timed entry. `--card N` accepts0..3; commands below show card2.
Use a new output directory per attempt; no automatic retry or failed-server loop.

```bash
nice -n 19 ionice -c 3 env -i LD_LIBRARY_PATH="$LD_LIBRARY_PATH" HOME=/home/steve PATH=/home/steve/.local/bin:/usr/bin:/bin XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus OMP_NUM_THREADS=2 /home/steve/.local/bin/python -B experiments/own-xpu-runtime/stage2/packet30-leftovers/window.py --authorized-device-window --window K0 --card 2 --output experiments/own-xpu-runtime/stage2/packet30-leftovers/build/k0-card2b
nice -n 19 ionice -c 3 env -i LD_LIBRARY_PATH="$LD_LIBRARY_PATH" HOME=/home/steve PATH=/home/steve/.local/bin:/usr/bin:/bin XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus OMP_NUM_THREADS=2 /home/steve/.local/bin/python -B experiments/own-xpu-runtime/stage2/packet30-leftovers/window.py --authorized-device-window --window G3 --card 2 --k0 experiments/own-xpu-runtime/stage2/packet30-leftovers/build/k0-card2b/window.json --output experiments/own-xpu-runtime/stage2/packet30-leftovers/build/g3-card2b
```

The absolute Python interpreter and user-bus location above are verified on this
host (uid1000). The wrapper environment includes the user bus for systemd; the
native process receives only its narrower recorded allowlist.
The wrapper verifies the entire sealed source/binary closure, CPU gates, closed
environment, `ldd` under the exact native environment, and filesystem-only checks
for `libur_adapter_level_zero_v2.so`, `libumf.so`, and `libze_loader.so` in the
coordinator-supplied `LD_LIBRARY_PATH` before inspecting or creating a fault latch.
The path must be present and is forwarded unchanged; its SHA256 is recorded
and bound between K0 and G3. No library is loaded by this preflight. Device masks
are rejected. K0 binds boot/card/binary/environment/build identity. G3 cannot run
under a different identity. Child jobs use systemd user units with nice19,
idle I/O and no restart. The native command is `build/device/g3 --mode K0|G3
--card N --output PATH`; use the wrapper, which supplies admission and monitoring.

On a candidate mismatch, evidence is flushed and other candidates continue. On
an infrastructure failure or new GPU fault, report before graceful drain, stop
new submissions, retain evidence and do not hard-kill or retry. An undrained
owner remains for the coordinator to assess. The wrapper never resets/reboots.
Read [DEADLINES](DEADLINES.md) before assigning the window. Inspect the sorted
`timing-table.md`, raw events, failures and `dispatch-measured.json` together.

A native failure explicitly reporting `device_contacted:false`, after the child
exits and the full kernel-log delta has no entries, is an ordinary failed window
and creates no fault latch. Missing/uncertain contact evidence, journal failure,
device contact, and GPU fault signatures retain the existing latch behaviour.
The coordinator retired the original missing-path K0 latch; its unchanged
[evidence](evidence/20261012-k0-no-devices-missing-library-path/README.md) is retained.
These replacement windows have not run during the CPU-only repair.
