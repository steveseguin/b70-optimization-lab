# Packet 46 CPU expert prerequisite

An original AVX2 implementation of the current packed expert arithmetic, a
complete synthetic-expert CPU oracle gate, and a sustained processing benchmark.
[Arithmetic and evidence limits](SPECIFICATION.md) are binding. No model-weight
file, device, GPU query or service is used. No source in earlier packets changes.

Build and run only after **2026-10-17 02:55 UTC**, with the packet's exclusive
CPU-work slot. The helper checks cutoff, nice, affinity, disk reserve, source
closure and binary identity. It refuses an existing receipt directory.

From the repository root:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage2/packet46-specialized/cpu-expert/run.py build --output experiments/own-xpu-runtime/stage2/packet46-specialized/cpu-expert/evidence/build
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage2/packet46-specialized/cpu-expert/run.py test --output experiments/own-xpu-runtime/stage2/packet46-specialized/cpu-expert/evidence/test
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage2/packet46-specialized/cpu-expert/run.py bench --output experiments/own-xpu-runtime/stage2/packet46-specialized/cpu-expert/evidence/bench --seconds 2 --samples 5 --threads 24
```

Choose new receipt names when reproducing; never overwrite evidence. Builds are
one translation unit and a depfile, no copied runtime/CMake tree. Build outputs
are ignored and restorable from the recorded compiler command. The wrapper
requests 25 MB of disk headroom and keeps the shared 8 GB floor.

Results are pending until the protected time cutoff and the actual CPU runs.
Finite CPU fixture equality does not qualify nonfinite device behavior, a real
model run, a CPU/GPU mailbox or the one-card schedule. Expert-byte processing
GB/s must never be presented as measured DRAM bandwidth or model tok/s.
