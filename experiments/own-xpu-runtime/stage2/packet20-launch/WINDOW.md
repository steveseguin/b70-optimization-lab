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
  --authorized-device-window --card 3 --seconds 600 \
  --output experiments/own-xpu-runtime/stage2/packet20-launch/build/window-card3-a
```

Expected work duration remains **20–50 seconds**, an unmeasured planning
estimate. Add the packet13 first-use startup/JIT proxy of about **17 seconds**
when sizing the watchdog: 67 s total planning proxy. The **600 s child watchdog**
(default, allowed **300..1800 s**) is separate from the **<60 s reporting goal**.
Even the minimum watchdog is 4.48× that conservative proxy; default is 8.96×.
A complete verified run beyond 60 s passes with `total_goal_exceeded=true`.
There is no native 50 s admission cutoff or total device-work gate.

Native `startup_jit_ms` includes context/queue creation and executable SYCL bundle
materialization before short waits, plus accumulated per-method queue/graph/raw
module setup (including raw JIT). Each setup is counted once, not five times.
`device_work_ms` sums the existing device timestamp envelopes, which exclude
setup but **include host issuing gaps**; it is not pure kernel execution time.
`work_wall_ms` is total wall minus startup/setup and teardown. Native `wall_ms`
and `teardown_ms` are also retained, separately from watcher/postflight elapsed.
Completion polls now allow **5 s** after submission; native teardown allows 3 s.
Expiry retains ownership; it does not send a signal. The watcher requests one
SIGTERM only on its roomy watchdog or fault/monitoring/external-stop conditions,
then allows **60 s** before recording and leaving a still-running child.
Synchronous driver/JIT calls have no unsafe forced short-time cancellation.
The [complete deadline audit](../packet18-decode-v2/DEADLINES.md) covers both packets.
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

CPU-only reseal after the issuing compile (fusion evidence is reused unchanged):

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B \
  experiments/own-xpu-runtime/stage2/packet20-launch/issuing/build.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B \
  experiments/own-xpu-runtime/stage2/packet20-launch/build.py --seal-existing
```

The fresh wrapper suite has 27 tests, including slow normal completion, rejected
short watchdogs, exactly one signal at the actual watchdog and retained children.
No device ran. GNU/Intel fusion gates, fixtures, repeats, snapshots, binaries and
precise compile/link identities are reused only after their hashes verify.
