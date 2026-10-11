# Packet 23 coordinator windows: immutable parameters, r3

No device ran in this repair. Run from the repository root only after coordinator
admission. The coordinator supplies LD_LIBRARY_PATH. Each command uses a fresh
output directory; original build/k1a and build/w0 are preserved as evidence.
Order is K0, K1a, K1b, W0, W2, W3, then the optional W2d diagnostic.

The wrapper and CPU jobs stay at nice 19. `--native-nice N` controls only
the native child (0 through 19): W2/W3 default to **0**, all other windows
default to 19. W2/W3 tok/s is measured at normal native-process priority.
A transient systemd user service starts the native child; no sudo, renice of
an existing process, or host setting is used. `native-priority.json` records
and checks the actual value before exec. Signals target only that service’s
main process. The receipt also records the requested native priority and unit.
If the user service cannot start at the requested priority, the window fails;
there is no fallback or restart. K0/K1/W0 receipts remain mandatory.

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
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window K0 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-r3
```

## K1a

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window K1 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/k1a-r3 --k0 experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-r3/window.json
```

## K1b

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window K1 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b-r3 --k0 experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-r3/window.json --repeat-of experiments/own-xpu-runtime/stage2/packet23-fast/build/k1a-r3/window.json
```

## W0

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W0 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w0-r3 --k0 experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-r3/window.json
```

## W2

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W2 --native-nice 0 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w2-r3 --k0 experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-r3/window.json --input experiments/own-xpu-runtime/stage2/packet23-fast/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b-r3/window.json --w0 experiments/own-xpu-runtime/stage2/packet23-fast/build/w0-r3/window.json
```

## W3

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W3 --native-nice 0 --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w3-r3 --k0 experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-r3/window.json --input experiments/own-xpu-runtime/stage2/packet23-fast/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b-r3/window.json --w0 experiments/own-xpu-runtime/stage2/packet23-fast/build/w0-r3/window.json
```

## W2d

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet23-fast/window.py --authorized-device-window --window W2d --output experiments/own-xpu-runtime/stage2/packet23-fast/build/w2d-r3 --k0 experiments/own-xpu-runtime/stage2/packet23-fast/build/k0-r3/window.json --input experiments/own-xpu-runtime/stage2/packet23-fast/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet23-fast/build/k1b-r3/window.json --w0 experiments/own-xpu-runtime/stage2/packet23-fast/build/w0-r3/window.json
```
