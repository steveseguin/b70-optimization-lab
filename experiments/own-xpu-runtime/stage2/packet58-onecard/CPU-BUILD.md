# Packet58 CPU build and gates

From the repository root, using the installed GNU and Intel 2026.0 compilers:

```bash
P=experiments/own-xpu-runtime/stage2/packet58-onecard
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" prepare
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" gnu-host
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" device
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/cpu_cache_gates.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/test_engine_reset.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/python_gates.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/seal.py" --verify
```

The `device` build compiles but never executes a device binary. The build
script uses one compilation job and checks the 1.5 GB cap. Each compiler
receipt binds 173 source files and rejects source changes during compilation.
No model payload or device is opened by these commands.

The retained `k1-cpu.json` comes from the GNU host-only fixture adapter:
`build/gnu-host/p58-cache-fixtures --iterations 1 --output <new-scratch-dir>`.
It uses ordinary CPU allocations, including memory labeled pinned by the mock;
it makes no OS pin request. Its host timings are not hardware performance.
After rebuilding that binary, regenerate the CPU golden and bind its
`binary_sha256` before creating a new seal. Never run the device fixture here.

Final build footprint: 147,167,317 bytes. The two binary receipts bind their
exact source snapshots. Eight cache/expert gate runs pass, including ASan and
UBSan; 213,816 state checks and 36 expert cases per corresponding run.
The production submission adapter passes 24 placements across three grids.
The request-reset gate compares a prompt after another prompt against two
fresh processes: exact tokens and 40 retained files. The 44 Python checks
cover memory, windows, policy replay, metrics and evidence mutations.

`seal.py` creates the final seal only after every source-bound CPU gate and
binary matches. `--verify` reads it without launching anything. If rebuilding,
keep old evidence and use a new coordinator output directory; never reseal a
running packet. The original cold host-USM device access and full model remain
coordinator qualification work.
