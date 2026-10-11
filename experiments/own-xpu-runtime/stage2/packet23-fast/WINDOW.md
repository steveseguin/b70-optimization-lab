# Packet 23 coordinator windows

No device ran during preparation. Run from the repository root after coordinator
admission. LD_LIBRARY_PATH is supplied by the coordinator. No systemd wrapper or
shorter external timeout is required by these commands. Do not close the owning
shell while a retained child exists.

K1 requires two fresh executions on card 3. Each execution runs the GEMV fixture
owner and the non-GEMV fixture owners sequentially. W0 then checks cards 2+3
on the same boot and decode binary. Both gates are bound to environment, binary,
receipts and clean teardown. W1 is recommended but optional; W2/W3 check all
64 tokens and 384 layer fixtures against v2 themselves. There is no boot blacklist;
the packet-local fault latch refuses further windows on that boot, and the
coordinator owns boot-wide fault decisions. No automatic retry occurs.

W2/W3 use fusion on and token timing. W2d/W3d use launch profiling and are
**distorted diagnostics, never a tok/s claim**. Decode uses generated tokens
2..64 over the whole steady-clock decode span; per-token rows remain in receipts.
The wrapper exposes no decode throughput claim for diagnostic windows.

Every native child passes ldd inspection before any fault latch can be created.
NEO/unknown runtime keys are refused by the closed environment allowlist.
Memory uses current MemAvailable directly, requiring owned allocations plus
host-backed tables and the existing descriptor allocation allowance; no added
host reserve, GPUActive credit, settings change or cache drop.

## K1 (k1a)

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window K1 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/k1a
```

## K1 (k1b)

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window K1 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b --repeat-of experiments/own-xpu-runtime/stage2/packet23-fast/build/k1a/window.json
```

## W0 (w0)

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W0 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w0
```

## W2 (w2)

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W2 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w2 --input experiments/own-xpu-runtime/stage2/packet23-fast/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b/window.json --w0 experiments/own-xpu-runtime/stage2/packet23-fast/build/w0/window.json
```

## W3 (w3)

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W3 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w3 --input experiments/own-xpu-runtime/stage2/packet23-fast/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b/window.json --w0 experiments/own-xpu-runtime/stage2/packet23-fast/build/w0/window.json
```

## W2d (w2d)

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W2d --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w2d --input experiments/own-xpu-runtime/stage2/packet23-fast/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b/window.json --w0 experiments/own-xpu-runtime/stage2/packet23-fast/build/w0/window.json
```

## W3d (w3d)

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W3d --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w3d --input experiments/own-xpu-runtime/stage2/packet23-fast/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b/window.json --w0 experiments/own-xpu-runtime/stage2/packet23-fast/build/w0/window.json
```

## W1 (w1) — optional

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W1 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w1 --input experiments/own-xpu-runtime/stage2/packet23-fast/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b/window.json
```
