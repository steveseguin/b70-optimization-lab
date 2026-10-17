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

## October 17 CPU results

The build began after **02:55:17 UTC**; all testing and both sustained processes
finished by **02:56:00 UTC**. The protected cutoff was respected. The executable
is 170,872 B; its SHA-256 is
`ab4c2b2468651da8d5599b8ee15d02a50a22db8e6a4e4452317d9e9b45ba4721`.
The source closure was identical before/after compilation and after each action.

Both fresh exactness processes passed **27,587 checks**, including 18 complete
expert comparisons and 30 dedicated down edge cases. Every gate, up, activation
and down BF16 value matched the existing CPU oracle; sampled FP32 lanes and trees
also matched. Both output digests are `ea0eeaa89bce627`. These are synthetic
fixture results. [Build receipt](evidence/build/receipt.json),
[exactness receipt](evidence/test/receipt.json).

The sustained benchmark used 24 threads confined to CPUs 4–15,20–31, nice 19,
and a 284,928,000-byte packed fixture bank. Each fresh process ran five measured
samples lasting at least two seconds each. Every worker's actual affinity and
FP environment were checked before each sweep. [Full benchmark receipt and
samples](evidence/bench/receipt.json).

| Fresh process | Median complete experts/s | p10 experts/s | Median processed GB/s | p10 processed GB/s |
| --- | ---: | ---: | ---: | ---: |
| 0 | 1,957.456 | 1,647.757 | 3.873152 | 3.260361 |
| 1 | 2,691.348 | 2,396.904 | 5.325281 | 4.742674 |

These are **packed expert bytes processed**, not measured DRAM traffic. The
ten retained samples vary from 1,648 to 2,781 experts/s. The cause of that spread
was not isolated; neither the faster process nor the best sample is a hardware
limit or a model speed claim.

This implementation does **not** meet the [refined uniform-cache scenario's
CPU requirement](../CACHE-BUDGET.md): 18,157 experts/s and 35.9268 processed GB/s
at 60 target positions/s. Its two process medians fall short by roughly
9.3× and 6.7×. Actual route hit rates remain unknown, and a better CPU kernel may
change this result. The next CPU implementation lever is reducing codebook
gather/decode cost while retaining the same lane arithmetic; real per-layer
miss latency and CPU/GPU overlap still require separate qualification.

Finite CPU fixture equality does not qualify nonfinite device behavior, a real
model run, a CPU/GPU mailbox or the one-card schedule. Nonfinite oracle parity
remains explicitly false. No model weight, GPU query, device window, service or
host setting was used or changed.
