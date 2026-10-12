# Coordinator device windows — prepared, not run

No device binary was executed for this packet. Run these only in an owner-authorized
quiet window. `--card N` means the first of an adjacent pair (N and N+1).
The wrapper refuses visible foreign engine activity before launching either rank.
It does not use device discovery for that preflight; unreadable foreign-UID fdinfo
is recorded as a visibility limit. The coordinator must also reserve the pair.

Only supply the working `LD_LIBRARY_PATH`; no driver, selector or experimental
runtime variables. The closed environment below forwards PATH, OMP=2 and that
library path. Each binary receives an `ldd` preflight. Each prerequisite is bound
to boot ID, both binary hashes, card pair, environment and child receipt hashes.
Do not reuse receipts across a rebuild or boot. Use a new output directory for
each attempt; there is no restart or retry loop.

K windows use nice19 and idle I/O. **All W commands must start from a nice-0 parent.**
A nice19 shell cannot raise its own priority. The CPU preparer did not run any of
these commands. Model ranks request nice0 and idle I/O from that parent.

Affinity is inherited unchanged, so any W command can be prefixed with
`taskset -c "$WINDOW_CPUS"` using the coordinator-assigned CPU list. This packet
never chooses cores or raises priority itself. `LD_LIBRARY_PATH` is copied byte
for byte, including empty path components. No library-path fallback is substituted.

Set these shell variables in the coordinator's nice-0 shell, from repository root:

```bash
P="$PWD/experiments/own-xpu-runtime/stage2/packet37-merged2"
ORACLE="$PWD/experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective"
CARD=0
```

K0 compiles every image on both cards in two simultaneous, single-device JIT
processes, with no kernel execution or allocation. K1a/K1b use the packet29 fixture harness style with the complete linked
kernel registry, including p33 additions, in fresh processes. Each K1 window then runs
`p33-linked-fixtures` exactly once in a separate owner on the same first card,
after the first fixture process exits. Its 216 exact comparisons cover all 36
linked dense type/shape/split instantiations (18 type/shape families, six input
modes each). Both K1 windows must provide fresh process IDs, zero live/in-flight
owner teardown, and output bytes equal to the sealed host fixture digest. The
extra receipt/output are retained under `linked/`; the binary hash is part of
the common prerequisite identity. K2 keeps 200 repetitions and rotates full-size buffers for payloads above 8 MB.
It compares bytes on the card before selecting a dispatch table. The two
`dispatch-rank0.json` and `dispatch-rank1.json` files beside
`dispatch-measured.json` are identical aliases of that one-card measurement,
for both pipeline ranks. They do not claim independent timing on the other card.

```bash
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/window.py" --authorized-device-window --window K0 --card "$CARD" \
  --output "$P/build/k0-r37"
```

```bash
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/window.py" --authorized-device-window --window K1a --card "$CARD" \
  --output "$P/build/k1a-r37" \
  --k0 "$P/build/k0-r37/window.json" --dispatch "$P/dispatch-all-new.json"
```

```bash
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/window.py" --authorized-device-window --window K1b --card "$CARD" \
  --output "$P/build/k1b-r37" \
  --k0 "$P/build/k0-r37/window.json" --dispatch "$P/dispatch-all-new.json" \
  --k1a "$P/build/k1a-r37/window.json"
```

```bash
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/window.py" --authorized-device-window --window K2 --card "$CARD" \
  --output "$P/build/k2-r37" \
  --k0 "$P/build/k0-r37/window.json" --dispatch "$P/dispatch-all-new.json" \
  --k1a "$P/build/k1a-r37/window.json" \
  --k1b "$P/build/k1b-r37/window.json"
```

W0p is mandatory before any full-size concurrent model run. Both ranks stay alive
for all 1,000 exchanges, each launching 1,000 chained tiny increment kernels.
It checks 256 bytes per rank per exchange, local queue ownership and teardown.
At least one pair of native host command intervals must overlap. This establishes
concurrent process activity, not clock-synchronized GPU kernel overlap. Each rank
uses 256 device bytes and 256 pinned bytes plus the 135,168-byte shared mapping.

```bash
ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/window.py" --authorized-device-window --window W0p --card "$CARD" \
  --output "$P/build/w0p-r37" --k0 "$P/build/k0-r37/window.json"
```

Every model window uses the 87-token prompt, generates 64 target tokens and retains
8 × 48 layer fixtures. All 64 tokens and 384 fixtures must equal the v2 oracle
exactly. W2s is sequential generation (`draft=none`) through the sealed prepared path. W2n uses n-gram
guesses. W2d supplies the oracle's guesses and is **DIAGNOSTIC ONLY**, never a speed
result. W2c records per-rank class profiling, also diagnostic. The paired W2s-off
run supplies the matching prompt-overlap comparison.

```bash
ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/window.py" --authorized-device-window --window W2s --card "$CARD" \
  --output "$P/build/w2s-r37" --input "$P/build/input" --oracle "$ORACLE" \
  --dispatch "$P/build/k2-r37/run0/dispatch-measured.json" \
  --k0 "$P/build/k0-r37/window.json" --k1a "$P/build/k1a-r37/window.json" \
  --k1b "$P/build/k1b-r37/window.json" --k2 "$P/build/k2-r37/window.json" \
  --w0p "$P/build/w0p-r37/window.json"
```

```bash
ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/window.py" --authorized-device-window --window W2n --card "$CARD" \
  --output "$P/build/w2n-r37" --input "$P/build/input" --oracle "$ORACLE" \
  --dispatch "$P/build/k2-r37/run0/dispatch-measured.json" \
  --k0 "$P/build/k0-r37/window.json" --k1a "$P/build/k1a-r37/window.json" \
  --k1b "$P/build/k1b-r37/window.json" --k2 "$P/build/k2-r37/window.json" \
  --w0p "$P/build/w0p-r37/window.json"
```

```bash
ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/window.py" --authorized-device-window --window W2d --card "$CARD" \
  --output "$P/build/w2d-r37" --input "$P/build/input" --oracle "$ORACLE" \
  --dispatch "$P/build/k2-r37/run0/dispatch-measured.json" \
  --k0 "$P/build/k0-r37/window.json" --k1a "$P/build/k1a-r37/window.json" \
  --k1b "$P/build/k1b-r37/window.json" --k2 "$P/build/k2-r37/window.json" \
  --w0p "$P/build/w0p-r37/window.json"
```

```bash
ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/window.py" --authorized-device-window --window W2c --card "$CARD" \
  --output "$P/build/w2c-r37" --input "$P/build/input" --oracle "$ORACLE" \
  --dispatch "$P/build/k2-r37/run0/dispatch-measured.json" \
  --k0 "$P/build/k0-r37/window.json" --k1a "$P/build/k1a-r37/window.json" \
  --k1b "$P/build/k1b-r37/window.json" --k2 "$P/build/k2-r37/window.json" \
  --w0p "$P/build/w0p-r37/window.json"
```

```bash
ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/window.py" --authorized-device-window --window W2s --card "$CARD" \
  --output "$P/build/w2s-off-r37" --input "$P/build/input" --oracle "$ORACLE" \
  --dispatch "$P/build/k2-r37/run0/dispatch-measured.json" \
  --k0 "$P/build/k0-r37/window.json" --k1a "$P/build/k1a-r37/window.json" \
  --k1b "$P/build/k1b-r37/window.json" --k2 "$P/build/k2-r37/window.json" \
  --w0p "$P/build/w0p-r37/window.json" --prompt-overlap off
```

The expected durations in [DEADLINES.md](DEADLINES.md) are estimates only. K0/W0p
have 600-second watchdogs; other windows have 10,800 seconds. Every watchdog is
at least four times the estimate and at least 300 seconds. There is one launch
per rank per stage, no timeout-based relaunch and no hard kill.

Admission remains conservatively 97 GiB of MemAvailable before the model ranks
load. This is not a measured requirement for the new process model. Each rank
records owner allocations, plan/weight bytes, host VmRSS/RssAnon, readable DRM
memory counters, and before/after-load memory. Compare those receipts to determine
whether this merged runtime preserves packet32's measured shadow removal. The wrapper also stops if
combined rank anonymous memory exceeds 8 GiB. No memory setting is changed.

Only lines after the wrapper's own journal cursor can count as new kernel faults.
The preflight excerpt is evidence only; old reviewed fault lines never latch.
An admission, loader or argument refusal before the first child launch cannot
write a fault latch. After a child has launched, a new kernel fault or failed rank first latches `build/FAULT.json` for the boot and
writes failure evidence, then requests one cooperative stop through the shared
pipe. A loading rank is never signalled. A rank still busy after bounded draining
is retained and reported to the coordinator, with its owner and mapping intact.
There is no reset, reboot, retry or marker deletion in this packet. The coordinator
owns evidence-first recovery under the host rules. Inspect retained PIDs before
any further work. The wrapper polls kernel logs through drain and postflight.

Successful model receipts include emitted tokens, fixture hashes, binary/input/
dispatch identities, guesses, hits, misses, no-guesses, prompt time, redo time,
per-rank work/idle intervals and handover latency. Decode uses 63 intervals from
token 1 completion to token 64 completion. Script/class modes leave the speed
field empty. Native class totals include prompt, accepted, rejected and redo work.
Per-half rank receipts also include prepare time, enqueue time per family, waits,
major/minor faults, voluntary/involuntary context switches, affinity and load
average. Rank 0 owns the lookup residency pass. No device speed is claimed here.
The inherited packet32 memory admission remains conservative; this packet does
not retime its already measured shadow-removal result.
