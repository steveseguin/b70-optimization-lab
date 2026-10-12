# Packet 34 coordinator windows

Preparation ran CPU gates and compiled device programs only. No device ran and
no speed is claimed. Run these commands from `/home/steve/llm-optimizations`
inside the coordinator's authorized systemd user unit. Each output directory
must be new. Both windows use exactly one physical card; replace both `--card 0`
values together. Supply the installed compiler/runtime library path as
`LD_LIBRARY_PATH`. No other caller environment reaches either binary.

K0 builds linked kernel bundles on the selected device, without submitting a
kernel or explicitly allocating device memory. This coordinator operation is
separate from the CPU-only `build.py device` compilation done in preparation.
The prepared binary is `build/device/jit-smoke`.

```bash
nice -n 19 ionice -c 3 env -i LD_LIBRARY_PATH="${LD_LIBRARY_PATH:?supply installed runtime libraries}" /usr/bin/python3 -B experiments/own-xpu-runtime/stage2/packet34-replay-bench/window.py --authorized-device-window --window K0 --card 0 --seconds 1200 --output experiments/own-xpu-runtime/stage2/packet34-replay-bench/build/k0-r34
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
nice -n 0 ionice -c 3 env -i LD_LIBRARY_PATH="${LD_LIBRARY_PATH:?supply installed runtime libraries}" /usr/bin/python3 -B experiments/own-xpu-runtime/stage2/packet34-replay-bench/window.py --authorized-device-window --window R1 --card 0 --seconds 1200 --k0 experiments/own-xpu-runtime/stage2/packet34-replay-bench/build/k0-r34/window.json --output experiments/own-xpu-runtime/stage2/packet34-replay-bench/build/r1-r34
```

The wrapper first requires a sealed passing build, all five hash-bound passing
CPU/capture/lifetime/window/raw-capability gate receipts, current host and device
binary hashes, and unchanged packet34/upstream source hashes. Partial builds or
stale gate results cannot launch K0. Rerun `seal.py` after completing all gates
and after any preparation-source change.

The wrapper binds both binaries, the build receipt, selected card, boot and
closed environment to K0. It checks `ldd` with that exact library path before
launch. Caller input permits only `LD_LIBRARY_PATH`; Python's automatically added
`LC_CTYPE=C.UTF-8` is accepted and discarded. Caller `PATH`, `OMP_NUM_THREADS`,
other locale values and all other variables are rejected. The wrapper supplies
internal `OMP_NUM_THREADS=2` and `PATH=/usr/bin:/bin`.
It does not discover devices or modify device selectors, host settings or
power settings. Device selection belongs to the authorized native owner.

Kernel fault signatures and journal-access failure latch the boot. The wrapper
saves failure before sending at most one cooperative SIGTERM. A 60-second drain
budget follows; a still-busy child is retained, with its PID and native logs.
There is no hard kill, reset or retry. SIGINT/SIGTERM to the wrapper follow the
same path. Do not release a retained owner or launch another window before the
coordinator handles the fault. Each native failure is recorded before native
teardown. Normal success additionally requires the safe-teardown receipt.

`build/k0-r34/window.json` and `build/r1-r34/window.json` are the wrapper receipts;
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
