# Packet 24 coordinator windows

Prepared only. No device window was run to produce this packet, and there is no
packet 24 speed claim. Run these commands from the repository root only when the
coordinator admits the cards. The coordinator supplies `LD_LIBRARY_PATH` externally.
All output directories must be new. A failed window latches this boot; it never
retries, resets a device, hard-kills a process, or changes host settings.

Order: K0, K1a, K1b, K2, W0, W2, W3, W2k. K0 builds the JIT bundle on cards 2 and 3
without a queue or kernel submission. Rebuilding, rebooting, or changing the
recorded environment invalidates K0. K1 uses card 3: the GEMV component has one
owner, and non-GEMV has four sequential owners (inherited fixtures, actual adapter,
route edge cases, staged kernel fixtures). K1b must match K1a from fresh processes.
All owners must release their allocations and events. Additional kernel and route
output hashes and exact coverage counts are checked against the sealed host gates.

The CPU prerequisite is a fresh packet 24 one-card streaming eight-token run with
`--kernels v2`: 384 exact layer fixtures and eight exact generated tokens. Carried
long two-card CPU receipts apply only to `--kernels v1`; they cannot admit v2.

K2 uses one card, synthetic non-GEMV data, and the earlier tiled packed-weight
fixtures for GEMV. It runs both kernel versions with 200 repetitions per registered
launch group. GPU time is the sum of `command_end - command_start` for each event
in a launch group, excluding gaps. `run/TABLE.md` shows median and nearest-rank p90,
sorted by weighted milliseconds per token within each version. `sequence-wall.jsonl`
records 200 complete per-layer issue sequences with one wait at the end. These are
synthetic profiling diagnostics, not model decode measurements. The wrapper calls
`k2.py` to validate full repetition coverage and produce the table after teardown.

W0 is a two-card canary. W2 and W3 run two-card 64-token decode with `--kernels v2
--fusion on --timing token`; W2 retains frozen GEMV and W3 uses R5. Both must match
the oracle's 64 tokens and 384 retained layer fixtures. W2k repeats W2 with
`--timing launch`, recording per-class spans. Its receipt is explicitly profiling;
the wrapper suppresses its decode speed headline. The same memory admission,
closed environment, hash bindings, fault journal, bounded SIGTERM drain, and
failure receipts apply. A pending child is retained for coordinator recovery.

Expected durations and submission/watchdog budgets are in [DEADLINES.md](DEADLINES.md).
Estimates are reported only and never trigger a stop.

## K0

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet24-kernels/window.py --authorized-device-window --window K0 --output experiments/own-xpu-runtime/stage2/packet24-kernels/build/k0
```

## K1a

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet24-kernels/window.py --authorized-device-window --window K1 --output experiments/own-xpu-runtime/stage2/packet24-kernels/build/k1a --k0 experiments/own-xpu-runtime/stage2/packet24-kernels/build/k0/window.json
```

## K1b

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet24-kernels/window.py --authorized-device-window --window K1 --output experiments/own-xpu-runtime/stage2/packet24-kernels/build/k1b --k0 experiments/own-xpu-runtime/stage2/packet24-kernels/build/k0/window.json --repeat-of experiments/own-xpu-runtime/stage2/packet24-kernels/build/k1a/window.json
```

## K2

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet24-kernels/window.py --authorized-device-window --window K2 --output experiments/own-xpu-runtime/stage2/packet24-kernels/build/k2 --k0 experiments/own-xpu-runtime/stage2/packet24-kernels/build/k0/window.json --input experiments/own-xpu-runtime/stage2/packet24-kernels/build/k2-input --k1 experiments/own-xpu-runtime/stage2/packet24-kernels/build/k1b/window.json
```

## W0

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet24-kernels/window.py --authorized-device-window --window W0 --output experiments/own-xpu-runtime/stage2/packet24-kernels/build/w0 --k0 experiments/own-xpu-runtime/stage2/packet24-kernels/build/k0/window.json
```

## W2

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet24-kernels/window.py --authorized-device-window --window W2 --output experiments/own-xpu-runtime/stage2/packet24-kernels/build/w2 --k0 experiments/own-xpu-runtime/stage2/packet24-kernels/build/k0/window.json --input experiments/own-xpu-runtime/stage2/packet24-kernels/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet24-kernels/build/k1b/window.json --w0 experiments/own-xpu-runtime/stage2/packet24-kernels/build/w0/window.json
```

## W3

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet24-kernels/window.py --authorized-device-window --window W3 --output experiments/own-xpu-runtime/stage2/packet24-kernels/build/w3 --k0 experiments/own-xpu-runtime/stage2/packet24-kernels/build/k0/window.json --input experiments/own-xpu-runtime/stage2/packet24-kernels/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet24-kernels/build/k1b/window.json --w0 experiments/own-xpu-runtime/stage2/packet24-kernels/build/w0/window.json
```

## W2k

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet24-kernels/window.py --authorized-device-window --window W2k --output experiments/own-xpu-runtime/stage2/packet24-kernels/build/w2k --k0 experiments/own-xpu-runtime/stage2/packet24-kernels/build/k0/window.json --input experiments/own-xpu-runtime/stage2/packet24-kernels/build/input --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --k1 experiments/own-xpu-runtime/stage2/packet24-kernels/build/k1b/window.json --w0 experiments/own-xpu-runtime/stage2/packet24-kernels/build/w0/window.json
```
