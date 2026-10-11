# First one-card IQ3 kernel window — prepared, not run

This packet's authorization is CPU tests and SYCL compilation only. The
following is for the next **separately authorized** native window. Coordinate
an exclusive physical card after the current baseline releases it; identify
its PCI/card mapping and obtain fresh health admission under local-ops. Do
not probe or interrupt another lane. No model server belongs in this test.

The resource owner's old tiny native smoke passed on October 11; it did not
test this new compute submission interface. Native dequant/GEMV exactness,
FP32 reduction parity, invalid-route safety and teardown under compute are
the question for this window. Performance is not a pass criterion.

## Prepare on CPU

Run from repository root, using installed oneAPI dependencies and no downloads:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet2/validate.py --keep-build
```

This regenerates and CPU-validates 27 device fixtures: two synthetic matrices
per supported type (BF16 and F16 inputs/outputs, varied signs/scales/codebook
indices), plus four rows of one real tensor per seven actual GGUF types.
It binds source, fixture and binary hashes in the build/CPU receipts.
Native testing reads these owned CPU fixtures, not the USB model files.
Set up the installed oneAPI environment in that authorized shell
(`source /opt/intel/oneapi/setvars.sh`); the resource owner's native receipt
records that the Level Zero adapter also needs the installed UMF library.
No fallback runtime, image, tool download or driver change is permitted.

After the coordinator admits physical card 0, the **first device command** is:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet2/tests/device_window.py --authorized-device-window --card 0 --output experiments/own-xpu-runtime/stage2/packet2/build/first-device
```

Use the admitted card index if it differs; record the physical mapping.
The output directory must be new. This command is not run during preparation.
The watcher launches exactly one child with `--authorized-device-window`;
there is no native test registered in CTest. It verifies hashes before launch,
saves boot/card/PID identity, captures a kernel-journal cursor and polls new
lines every 250 ms (journal commands have a two-second timeout). The native
child bounds work to at most 32 four-row fixtures and ten-second event waits;
the controller requests a cooperative stop after 120 seconds. Neither timeout
permits freeing live storage or hard-killing the child. Driver calls can
still block; a refused drain holds ownership for the coordinator.

One in-order compute queue, one card, no graph, peer transfer or background
worker. Arena allocations are just bounded packed samples, device activations,
dequant/accumulator/output buffers, routing/status arrays and pinned copy
slabs. Each test releases its allocations after all its events complete.
The census records every requested category; driver shadows remain unknown.
The largest four-row sample is under 128 KiB, and per-case Arena requested
memory is below 1 MiB. Codebooks and driver/compiler overhead are additional.

For each fixture, run subgroup 16 and 32, with both original activations and
sign-mutated activations plus changed expert IDs/spans: **108 checks**. Each
check compares FP32 dequant bytes, FP32 GEMV accumulator bytes and final
F16/BF16 output bytes against the shared CPU path. A two-expert/four-row
bank tests device routing, multiple spans, unused output tails and an invalid
expert/row descriptor; invalid routes must produce status 1 and canonical
NaNs without reading bank/input. The ordinary and routed GEMV both export
FP32 diagnostic buffers in this test, so 16-bit rounding cannot hide a drift.

## Pass criteria

1. All 108 checks pass bit-for-bit, with both subgroup layouts and changed
   inputs/routes; no missing real type or synthetic-only requested format.
2. Zero invalid-pointer access; all valid route statuses zero, deliberately
   invalid route status one, poisoned tail sentinels as specified.
3. Every event is tracked by Device; orderly drain, all allocations released,
   final idle marker complete, events/queue/context released in order;
   `safe_to_exit=true`, zero live bytes/in-flight work and child exit code 0.
4. No new `Fault response`, CAT error, engine reset, device coredump, GuC
   lockup or timed-out GPU job/fence in startup/run/postflight. Watcher success
   is provisional until the coordinator independently confirms card idle and
   fresh health, retaining the complete journal and external admission receipts.
5. Retain binary/source/compiler flags, original CPU fixtures/hashes, all
   outputs, census, teardown and watcher receipts under an evidence directory
   before any scratch cleanup. Repeat in a fresh native process only as a
   preregistered second stage after this first clean gate; the first command
   contains no automatic retry. Full native operator/model determinism remains
   a later gate even if this small sample passes.

On the first fault, journal failure, mismatch, timeout or signal: stop new
submissions, save evidence, send **one** cooperative signal to the captured
PID if needed, drain and report failure. Do not restart, force-kill, reload a
driver, clear a coredump, reset or reboot. If cleanup cannot establish safety,
keep ownership alive for the coordinator. A first fault's later bounded
recovery probe follows the owner's rules within that future authorized
window; this CPU preparation authorizes no probe. Never cycle the running
baseline or touch port 8188/LTX units.
