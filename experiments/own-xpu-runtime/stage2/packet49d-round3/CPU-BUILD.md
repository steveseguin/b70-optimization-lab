# Packet49d CPU preparation

Run from this packet directory. No device binary is executed here. All builds
are serial, at nice 19 on cores 4–15,20–31 with two OpenMP threads. Keep the new
build under 1.5GB; no cleanup may reach another packet or protected chain.

```bash
cpu49d() {
  nice -n 19 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B "$@"
}
cpu49d storage_precheck.py
cpu49d build.py prepare
cpu49d build.py gnu-host --jobs 1
cpu49d p49c_engine_gate.py
cpu49d build.py device --jobs 1
cpu49d cleanup_objects.py
cpu49d build.py asan --jobs 1
cpu49d cleanup_objects.py
cpu49d p49_cpu_gate.py
cpu49d p49_plan_gate.py
cpu49d p49_snapshot_gate.py
cpu49d p49_python_gate.py
cpu49d p49_asan_gate.py
cpu49d p49b_expert_gate.py
cpu49d p49c_round2_gate.py
cpu49d p49d_cpu_gate.py
ASAN_OPTIONS=halt_on_error=1:detect_leaks=1 \
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
P49_SNAPSHOT_MODE=asan cpu49d p49_snapshot_gate.py
cpu49d cleanup_objects.py
cpu49d retain_sanitizers.py
```

The sanitizer build compiles only the five executables used by its gates:
`own-rt-iq3`, `p49-qsa-fixtures`, `p49b-expert-fixtures`, `p49c-fixtures` and
`p49d-fixtures`. All use unchanged ASAN/UBSAN instrumentation and arithmetic
flags. GNU and device builds include every target. Cumulative object cleanup
keeps the compilation and archive coexistence peaks within the build cap.

The source revision is recorded in `runtime-revision.json` after committing the
reviewed implementation. The preparation seal binds this identity independently
from the later selected configuration. Source and binary changes invalidate gates.
Only regenerable scratch owned by this packet may be removed; retain all receipts.

After gates and recorded cleanup, write the actual storage observation and seal:

```bash
cpu49d storage_precheck.py > storage-precheck.json
cpu49d p49_seal.py
cpu49d p49_seal.py --verify-cpu
```

The initial seal is `cpu-preparation-seal.json`. It does not create a device-ready
`build-receipt.json`. Use [WINDOW.md](WINDOW.md) for the coordinator's selection
and fast reseal after the packet54 decision. No new oracle build or run is needed.

`p49d-fixtures` exercises production and every selectable alternative through
actual submitters, including M=1, serial M=2 state, controls, invalid positions,
invalid routes and admission refusals. Each compared allocation must match
production byte for byte. NaN/Inf scenarios 6/7 are compared on each backend
but omitted from the portable CPU/device digest; their case records remain.
This prevents backend-specific NaN representation from masquerading as a
candidate failure or an arithmetic tolerance. Finite and subnormal cases remain
in the portable digest. The actual-engine gate additionally checks complete
ordinary GDN/QSA layers with banked paths versus packet49c production controls.
Prepared capture/replay and full-model gates remain required device work.
