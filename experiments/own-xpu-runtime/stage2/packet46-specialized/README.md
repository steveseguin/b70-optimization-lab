# Packet46: specialized layers and exact CPU experts

Bounded preparation for the lab's own IQ3 engine. This packet adds static
ordinary-GDN and QSA compositions over packet45's current kernels, a standalone
AVX2 expert path, and optional route/phase diagnostics. Packet45 is read-only.
No model file or GPU is used by preparation. **Device exactness and performance
remain coordinator work**, regardless of CPU test results.

The source and [preregistration](PREREGISTRATION.md) preserve arithmetic-v2,
full BF16 KV/state, original intermediates and reduction trees. One-card
synthetic layer windows compare the 35-launch ordinary GDN and 41-launch QSA
baseline with the specialized compositions at M=1 and occupied 4K context.
The later integration bar is 80 microseconds saved per layer in **both** fresh
GPU timing owners, after every-intermediate/full-state raw-byte gates.

| Part | Entry point |
| --- | --- |
| Layer composition | [design](kernel-design.md), [specialized.hpp](specialized.hpp), [layer owner](layer_bench.cpp) |
| CPU expert arithmetic and benchmark | [specification](cpu-expert/SPECIFICATION.md), [commands](cpu-expert/README.md) |
| Cache budget and fixed initial placement | [refinement](CACHE-BUDGET.md), [exact metadata](cache-budget.json) |
| Route/phase schema and adapter | [diagnostics](diagnostics/README.md) |
| Card-0 coordinator command files | [WINDOW.md](WINDOW.md) |
| Results and remaining risks | [October 17 note](../../../../notes/2026-10-17-own-runtime-packet46.md) |
| Closed CPU throughput question | [closeout](CPU-EXPERT-CLOSEOUT.md), [negative-result index](DO-NOT-REPEAT.md) |

This is a lab packet, not a portable model package or speed claim. The layer
build validates and relinks existing packet45 dependency objects read-only;
it does not silently trust the mutable nightly tag or source timestamps.
Baseline source, checked include mirror, precision flags and artifacts are
hash-bound. Only new packet46 outputs are writable. CPU fixture expert bytes
come from the existing lab generator, not from a new model-weight read.

## CPU preparation

The runner refuses compilation or sustained tests before **October 17,
02:55 UTC**. It requires nice 19, CPUs 4–15,20–31 and a nonblocking shared
packet46 CPU-work lock. Run these sequentially from the repository root,
stopping at the first failure. Never run a device binary to test compilation.

```bash
P46=experiments/own-xpu-runtime/stage2/packet46-specialized

nice -n 19 taskset -c 4-15,20-31 python3 -B "$P46/cpu-expert/run.py" build \
  --output "$P46/cpu-expert/evidence/build"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P46/cpu-expert/run.py" test \
  --output "$P46/cpu-expert/evidence/test"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P46/cpu-expert/run.py" bench \
  --seconds 2 --samples 5 --threads 24 --output "$P46/cpu-expert/evidence/bench"

nice -n 19 taskset -c 4-15,20-31 python3 -B "$P46/diagnostics/run_cpu.py" \
  --output "$P46/diagnostics/evidence/cpu-gate"

nice -n 19 taskset -c 4-15,20-31 python3 -B "$P46/build_layer.py" --kind host
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P46/cpu_layer_gate.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P46/build_layer.py" --kind device
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P46/cpu_checks.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P46/seal.py"
```

The evidence directories are write-once. For a deliberate later reproduction,
choose new evidence directories, preserve the old receipts and update the
seal's explicit receipt paths in a reviewed new packet revision. A failure
is never automatically retried. The expert and full-layer CPU gates use two fresh processes.
Layer CPU tests are full production geometry using synthetic fixtures, not a
miniature model quality claim. The short Python gates are admission/schema
tests and touch no native backend.

## Storage and evidence

Build output is ignored. Baseline dependency objects are read-only and shared;
only packet46's new objects, linked binaries and relink proof are added.
The build's admitted write allowance is 1 GB per layer mode and preserves
the inherited 8 GB free-disk floor. Full-layer CPU tests retain compact JSONL
comparisons, receipts and logs in tracked `evidence/cpu-layer-TIMESTAMP/`
directories; no buffer dumps are retained. Compiled binaries remain ignored.
CPU evidence retains hashes rather than a duplicate full model/state tree. No original
evidence is deleted to reclaim space. The source, commands and pinned parent
build are needed to restore these local binaries.

Every exactness comparison records the byte count and SHA256 after a raw byte
comparison. The frozen ordered capture manifest binds producer boundaries and
all mutable allocations, including temporary workspace and padding. Timing
keeps every event's endpoints and class, and compares complete state outside
the measured region for every input pair. A timing window can complete safely
while failing the 80 microsecond bar; both facts remain visible.

The AVX2 benchmark reports **packed expert bytes processed per second** and
complete experts per second, with two fresh-process sample sets. It does not
measure DRAM bandwidth, layer miss tails, PCIe overlap or emitted tokens/s.
Nonfinite CPU/device oracle parity is explicitly pending; candidate guard
tests cannot qualify that behavior. The cache budget remains a design, and
its hypothetical hit rate remains unmeasured until valid IQ3 traces exist.

Credit Niko1221 / Strata for the hot-expert GPU cache and CPU-miss arrangement
already recorded in [ONE-CARD-DESIGN](../../ONE-CARD-DESIGN.md). All code here
is independently authored from the lab's own runtime and arithmetic contracts.
No Strata source was read, copied or ported.
