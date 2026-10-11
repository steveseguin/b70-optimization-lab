# Prepared one-card window — do not run during FAULT HALT

No device program was executed to prepare this packet. The existing fault halt
and parked PID 183867 are untouched. This command is for the coordinator only,
after a separately authorized recovery and exclusive one-card health admission.
It does not perform recovery, driver reset, service management or retries.

From repository root, with card **3** as the example (replace only `--card` with
an admitted physical index 0–3):

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 \
  LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.0/lib \
  python -B experiments/own-xpu-runtime/stage2/packet20-launch/device_window.py \
  --authorized-device-window --card 3 \
  --output experiments/own-xpu-runtime/stage2/packet20-launch/build/window-card3-a
```

Expected duration: **20–50 seconds of work plus 3 seconds of journal postflight**,
a planning estimate, not a measured duration. Native admission stops at 50 s;
each completion poll is bounded at 900 ms. The watcher requests one cooperative
stop at 50 s, allows 5 s to drain, and retains a stuck child for the coordinator.
It never kills the process. Synchronous driver discovery/JIT/API calls cannot
be given a guaranteed wall bound without unsafe forced termination. Therefore
healthy completion under 60 s remains a device gate, not a proven promise.
Every kernel does only 2,560 lanes of trivial work; no model weights are loaded.

Explicit device arrays are small (17 × 5,120 bytes before auxiliary buffers),
well below 64 MB. Graph/list/runtime/JIT reservations are opaque and are not
bounded by that explicit census. A strict **total** device-memory <64 MB limit
is unproven until the driver accounting is measured. Do not treat this packet
as evidence that opaque reservations fit that bound.

`ldd` and source/binary/SPIR-V hashes are checked before any latch is created.
The kernel-journal cursor is captured before the one child starts. A new fault,
journal failure, deadline, output mismatch, missing row or unsafe teardown
leaves `build/device-fault-latch.json` and refuses another window. No failure
causes an automatic restart. Never delete a failed latch merely to rerun.
A passing run removes its in-progress latch only after full checks.

The native program writes 270 JSON rows, with logical N, physical launches,
five repeat indices, wall timing, device timing definitions, setup time and
exact output verification. Graph/native replay consume changed device state.
`device.json` and `window.json` must both pass, the full matrix must be present,
and the final journal must stay clean. A compiler-available API may still be
unsupported by the installed B70 driver; record that as an unavailable arm,
never silently substitute a different issuing method.

CPU-only inspection, safe while halted, uses the same command with `--check`
in place of `--authorized-device-window`. It runs `ldd`, never the binary or
a device query, and does not create an admission latch.

A second fresh-owner window is a separate future command and is needed for a
speed verdict. Packet20 does not schedule it, publish a throughput number or
select a production graph based on one microbenchmark process.
