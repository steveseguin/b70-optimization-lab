# Packet49c CPU preparation

Run from this packet directory. Never execute a device binary in preparation.
All compiles are serial, at low priority alongside the existing CPU oracle.
The build links admitted packet45 metadata and fixtures read-only; the oracle
symlink points at packet49. No model payload is read.

```bash
cpu49c() {
  nice -n 19 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B "$@"
}
cpu49c storage_precheck.py
cpu49c build.py prepare
cpu49c build.py gnu-host --jobs 1
cpu49c p49c_engine_gate.py
cpu49c build.py device --jobs 1
cpu49c build.py asan --jobs 1
cpu49c p49_cpu_gate.py
cpu49c p49_plan_gate.py
cpu49c p49_snapshot_gate.py
cpu49c p49_python_gate.py
cpu49c p49_asan_gate.py
cpu49c p49b_expert_gate.py
cpu49c p49c_round2_gate.py
ASAN_OPTIONS=halt_on_error=1:detect_leaks=1 \
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
P49_SNAPSHOT_MODE=asan cpu49c p49_snapshot_gate.py
```

The sanitizer build keeps ASAN/UBSAN, frame pointers and symbol names, with
`-g0 -ffunction-sections -fdata-sections -Wl,--gc-sections`. This removes debug
line tables and unreachable duplicated entry points from fixture executables;
source-line stack traces are unavailable. GNU production and device arithmetic
flags are unchanged. Sanitizer checks are never disabled to meet storage.

After all gates, remove only this packet's regenerable objects using the
recorded cleanup, recheck storage, then seal and independently verify:

```bash
cpu49c cleanup_objects.py
cpu49c storage_precheck.py
cpu49c p49_seal.py
cpu49c p49_seal.py --verify
```

The final receipts, not inherited historical gate files, establish qualification.
Do not invoke the shared oracle's build/run actions.
