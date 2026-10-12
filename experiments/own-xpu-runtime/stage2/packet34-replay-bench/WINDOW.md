# Packet 34 coordinator windows

Preparation ran CPU gates and compiled device programs only. No device ran and
no speed is claimed. Run these commands from `/home/steve/llm-optimizations`
inside the coordinator's authorized systemd user unit. Each output directory
must be new. Both windows use exactly one physical card; replace both `--card 3`
values together. Supply the installed compiler/runtime library path as
`LD_LIBRARY_PATH`. No other caller environment reaches either binary.

K0 builds linked kernel bundles on the selected device, without submitting a
kernel or explicitly allocating device memory. This coordinator operation is
separate from the CPU-only `build.py device` compilation done in preparation.
The prepared binary is `build/device/jit-smoke`.

The coordinator reviewed this boot's old incidents through the following UTC
instant. Set this shell variable for **both** commands; do not replace it with
“now” without a new coordinator review. A local time without its UTC offset is
rejected. K0 and R1 must bind the same normalized review instant.

```bash
REVIEWED=2026-10-12T02:20:00Z
```

The refused October 12 `k0-r34` evidence and its retired preflight latch are
[archived](evidence/20261012-k0-refused-old-boot-fault-lines/README.md).
No process started in that attempt. Use the new output names below.

```bash
nice -n 19 ionice -c 3 env -i LD_LIBRARY_PATH="${LD_LIBRARY_PATH:?supply installed runtime libraries}" /usr/bin/python3 -B experiments/own-xpu-runtime/stage2/packet34-replay-bench/window.py --authorized-device-window --window K0 --card 3 --faults-reviewed-through "$REVIEWED" --seconds 1200 --output experiments/own-xpu-runtime/stage2/packet34-replay-bench/build/k0-r34b
```

R1 runs the half-token benchmark: direct, one whole-half-token graph, then
24 layer graphs. Every replay mode first requires the same-process direct
reference. Each mode uses 10 warm-ups and 200 measured iterations. Raw regular
list replay is blocked; there is no raw option or silent fallback.

Run R1 from a nice-0 parent. A nice-19 parent cannot raise its own priority.
The coordinator may put this command under `taskset` on its reserved cores;
the wrapper and child preserve that inherited affinity and priority. Helper
processes (`ldd` and journal reads) run at nice 19 with idle I/O priority.
The preparatory agent must never run R1 or change its own affinity/priority.

```bash
nice -n 0 ionice -c 3 env -i LD_LIBRARY_PATH="${LD_LIBRARY_PATH:?supply installed runtime libraries}" /usr/bin/python3 -B experiments/own-xpu-runtime/stage2/packet34-replay-bench/window.py --authorized-device-window --window R1 --card 3 --faults-reviewed-through "$REVIEWED" --seconds 1200 --k0 experiments/own-xpu-runtime/stage2/packet34-replay-bench/build/k0-r34b/window.json --output experiments/own-xpu-runtime/stage2/packet34-replay-bench/build/r1-r34b
```

The wrapper first requires a sealed passing build, all five hash-bound passing
CPU/capture/lifetime/window/raw-capability gate receipts, current host and device
binary hashes, and unchanged packet34/upstream source hashes. Partial builds or
stale gate results cannot launch K0. Rerun `seal.py` after completing all gates
and after any preparation-source change.

The wrapper binds both binaries, the build receipt, selected card, boot,
closed environment and review instant to K0. It checks `ldd` with that exact
library path before launch. Caller input permits only `LD_LIBRARY_PATH`; Python's automatically added
`LC_CTYPE=C.UTF-8` is accepted and discarded. Caller `PATH`, `OMP_NUM_THREADS`,
other locale values and all other variables are rejected. The wrapper supplies
internal `OMP_NUM_THREADS=2` and `PATH=/usr/bin:/bin`.
It does not discover devices or modify device selectors, host settings or
power settings. Device selection belongs to the authorized native owner.

With `--faults-reviewed-through`, the initial fault scan uses `journalctl
--since @epoch` at one microsecond after that instant (journal timestamps have
microsecond resolution). Epoch syntax avoids the host's local timezone.
`window.json` records `coordinator_fault_review` with `through`, `lines_before`
and `fault_lines_before`: the latter two count boot journal entries at or before
the boundary, and matching entries among them. The full initial boot snapshot
is retained as `kernel-boot-before-review.txt`; `kernel-before.txt` contains the
entries after review. The watcher then checks new lines after its journal cursor.
An empty reviewed interval retains the initial boot cursor.

Without the argument, old fault lines still refuse admission. If every matching
line is more than one hour older than the wrapper's start and no packet 34
native launch was attempted on this boot, refusal asks for coordinator review
without writing a latch. Current and archived window receipts are checked;
a persisted command counts conservatively as a launch attempt. Recent lines,
old lines after a packet 34 launch, and any fault after the supplied review
instant still latch. An existing boot latch always blocks, even with review.

During supervision, kernel fault signatures and journal-access failure latch
the boot. The wrapper saves failure before sending at most one cooperative SIGTERM. A 60-second drain
budget follows; a still-busy child is retained, with its PID and native logs.
There is no hard kill, reset or retry. SIGINT/SIGTERM to the wrapper follow the
same path. Do not release a retained owner or launch another window before the
coordinator handles the fault. Each native failure is recorded before native
teardown. Normal success additionally requires the safe-teardown receipt.

`build/k0-r34b/window.json` and `build/r1-r34b/window.json` are the wrapper receipts;
`run/receipt.json`, `native.txt` and kernel logs retain native evidence. A passing
native work receipt does not make an abnormal exit a passing window.

K0 has no kernel submissions and its unchanged compile-smoke program has no
cooperative signal handler. On a K0 stop request the wrapper records failure and
retains the compiling child without sending SIGTERM. The coordinator owns that
child until compilation returns; it must not be killed during native compilation.

The watcher sums `RssAnon` for the native child and its descendants, including
children created by JIT helper threads, by reading `/proc` directly. It starts
the stop protocol at 7.5 GiB, leaving 512 MiB below the 8 GiB bound. The receipt
retains the sampled peak and last process list. This is a polling safeguard,
not a host memory limit; it changes no host setting and never kills a GPU job.
A failed memory sensor also stops the window. R1 validates all iteration and
recording rows through `summarize.py` before passing and binds the resulting
`run/summary.json` hash. A passing window need not mean replay pays; the summary
reports that measured verdict separately.
