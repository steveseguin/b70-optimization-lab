# One-launch packed-read diagnostic

`microbench.cpp` is compiled, never run during preparation. It uses real
head248,320 × 2,560 and QKV10,240 × 2,560 geometries with deterministic synthetic
packed rows. All initialization/copies happen before timing. This is an
operator diagnostic, never a model benchmark or a quality promotion gate.

The unchanged expanded path reads3200 useful bytes per row (3380 resident);
the candidate reads2100 packed bytes. Both keep eight columns per lane,
ten serial tiles, SG32 reduction, separate FP32 operations and BF16 output.
The expanded control uses packet33's32-item workgroup; the packed path uses
the engine candidate's256-item group. Thus this measures the proposed
one-launch implementation, including its geometry, not an isolated byte-only
ablation. An untimed FP32-output kernel pair requires byte-identical output
for every row before any speed samples. Timed kernels write BF16 only.

Each shape runs20 samples per arm, alternating order, and records both device
event time and submission/wait wall time. There is no extra unpack launch or
unreported final reduction. The large full head exceeds device cache; QKV
may benefit from cache and must be labeled an operator result. Repeat in two
fresh coordinator-owned processes before a speed verdict. Actual engine
screens decide usefulness.

Build only, with the installed Intel compiler:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet74-packed-dense/build_microbench.py </dev/null
```

After the coordinator's ordinary ownership, fault, masking and idle-card
admission, the binary accepts exactly:

```text
experiments/own-xpu-runtime/stage2/packet74-packed-dense/build/microbench --coordinator-admitted-device-window
```

Run it inside the coordinator's existing bounded device window, with one
visible admitted GPU, fault monitoring and graceful teardown; this direct
binary is not a replacement for that wrapper. No automatic run, retry, queue
insertion, device discovery during build, or service was added. The build
receipt pins source closure, flags and binary SHA256.
