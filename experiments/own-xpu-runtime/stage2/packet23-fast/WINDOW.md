# Packet 23 coordinator windows after the capture repair

No device ran in this repair. Run from the repository root only after coordinator
admission. The coordinator supplies LD_LIBRARY_PATH. Each command uses a fresh
output directory; original build/k1a and build/w0 are preserved as evidence.
Order is K0, K1a, K1b, W0, W2, W3, then the optional W2d diagnostic.

K0 is one process. It builds every kernel for cards 2 and 3 and submits no work.
All four native programs link the same compiled kernel objects, with the same
precision flags, so its kernel bundle includes the exact main/canary and fixture
kernels. It creates no queue and performs no explicit USM allocation. Compiler
exceptions and their build logs are saved to stdout.txt and run/failure.json.
Expected under a minute is an estimate; watchdog is 600 seconds. A successful K0
receipt is mandatory on this boot and these binaries before every later window.
A rebuild, environment change or reboot invalidates that receipt.

K1a and K1b run the two fixture components sequentially on card 3, each in fresh
processes. W0 then checks cards 2+3. W2 and W3 compare 64 generated tokens and
384 layer hashes against v2. W2 uses frozen GEMV and W3 uses R5. W2d uses launch
profiling and is a distorted diagnostic, never a speed claim. No automatic retry,
reset, kill, or host-setting change is permitted. A genuinely pending event is
listed in failure.json and stderr before the owner waits for the coordinator.

## K0

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window K0 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-repair
```

## K1a

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window K1 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/k1a-repair --k0 experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-repair/window.json
```

## K1b

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window K1 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b-repair --k0 experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-repair/window.json --repeat-of experiments/own-xpu-runtime/stage2/packet23-fast/build/k1a-repair/window.json
```

## W0

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W0 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w0-repair --k0 experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-repair/window.json
```

## W2

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W2 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w2-repair --k0 experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-repair/window.json --input experiments/own-xpu-runtime/stage2/packet23-fast/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b-repair/window.json --w0 experiments/own-xpu-runtime/stage2/packet23-fast/build/w0-repair/window.json
```

## W3

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W3 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w3-repair --k0 experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-repair/window.json --input experiments/own-xpu-runtime/stage2/packet23-fast/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b-repair/window.json --w0 experiments/own-xpu-runtime/stage2/packet23-fast/build/w0-repair/window.json
```

## W2d

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W2d --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w2d-repair --k0 experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-repair/window.json --input experiments/own-xpu-runtime/stage2/packet23-fast/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b-repair/window.json --w0 experiments/own-xpu-runtime/stage2/packet23-fast/build/w0-repair/window.json
```
