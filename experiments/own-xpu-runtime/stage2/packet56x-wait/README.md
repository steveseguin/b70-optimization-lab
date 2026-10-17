# Packet56x: device waits without 1 ms polling

Built from packet56w, with two lean sealed host wait policies. One CMake object
build supplies both device executables; only a separately linked policy constant
differs. No environment variable can override the policy. Seals bind each
executable separately. Kernels and arithmetic remain unchanged.

- **(a) spin:** `build/device/own-rt-iq3`, `screen-seal-spin.json`.
- **(b) sleep20:** `build/device/own-rt-iq3-sleep20`, `screen-seal-sleep20.json`.

See [wait audit](WAIT-AUDIT.md), [screen commands](WINDOW.md) and
[task note](../../../../notes/2026-10-17-own-runtime-packet56x.md).
Device exactness and speed remain pending coordinator screens.

CPU preparation from the repository root:

```bash
P=experiments/own-xpu-runtime/stage2/packet56x-wait
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/prepare_cpu_input.py"
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/build_spin.py"
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/cpu_gate.py"
```

Only these build/gate entry points apply; inherited helpers retain historical
context. Never overwrite a screen seal after use. Reproduction needs Intel
oneAPI 2026.0 icpx, CMake, g++ and OpenSSL. The inherited CPU RoPE header is
restorable from the retained RoPE bytes using prepare_cpu_input.py, checked
against packet56w's sealed hash. Generated build files are ignored; source,
commands, build logs, exact fixtures and receipts are retained here.

Both variants passed 1,123 controller cases, five mailbox fault checks, seven
wait checks, a 765-byte packet56 fixture comparison, separate seals and screen
v1 CPU plans. [CPU closeout](CPU-PREPARATION-CLOSEOUT.md). Retained build: about
60 MB; only regenerable local objects were removed. After the CPU gates, run
`nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal_and_plan.py"` once to
create both seals and the saved plans.
