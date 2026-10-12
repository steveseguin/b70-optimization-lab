# CPU preparation and final sealing

Run from the repository root with the inherited CPU affinity. These commands
never execute a device program. At most two compilation jobs and four CPU-bound
processes are permitted; the simplest reproduction is serial. Every Python
invocation uses `-B`. The packet requires NumPy in the lab Python environment,
GNU C++, Intel oneAPI 2026.0, the pinned local target input files, and the official
draft shards listed by `official-tensors.json`. No download is implicit.

```bash
set -e
packet38=experiments/own-xpu-runtime/stage2/packet38-integrated
packet38_python=/home/steve/.venvs/vllm-xpu/bin/python
packet38_cpu() {
  nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 "$packet38_python" -B "$@"
}
packet38_cpu "$packet38/build.py" prepare
packet38_cpu "$packet38/build.py" gnu-host
packet38_cpu "$packet38/build.py" icpx-host
packet38_cpu "$packet38/build.py" asan
packet38_cpu "$packet38/build.py" device
packet38_cpu "$packet38/build_native_controller.py"
packet38_cpu "$packet38/cpu_campaign.py" cheap
packet38_cpu "$packet38/cpu_campaign.py" mini
packet38_cpu "$packet38/cpu_campaign.py" real-gnu
packet38_cpu "$packet38/cpu_campaign.py" real-intel
packet38_cpu "$packet38/cpu_campaign.py" real-native
packet38_cpu "$packet38/cpu_campaign.py" captures
packet38_cpu "$packet38/cpu_campaign.py" draft-final
packet38_cpu "$packet38/cpu_campaign.py" suite
```

These campaign phases reproduce the inherited parent gates and real-model
comparisons. Additional packet38 gates have their own named scripts and
source/binary-bound receipts: `native_controller_gate.py` for each normal and
sanitized controller binary, `native_mini_gate.py` without `--quick`,
`p38_kernel_gate.py`, `suite_gates.py`, `window_cpu_gate.py`, and the focused
`test_*.py` regression checks named in `cpu-tests.json`. The latter receipt is
the exact gate inventory; campaign completion alone cannot produce a seal.
`native_mini_gate.py` takes `--binary build/gnu-host/own-rt-iq3` and a fresh
`--output` path. Suite and window gates likewise accept fresh `--output` paths.
Archive completed gate scratch with `storage.discard` before the next stage.

The retained `suite-cpu-manifest.json` and `suite-cpu-freeze.json` pin the partial
real CPU suite. Do not silently substitute a growing live manifest into that
receipt. `cpu_campaign.py suite` runs this frozen snapshot in two persistent
Intel host ranks and archives it after exporting exactness evidence. Before
launch, all five Intel real-model mode receipts must pass with the current
binary and their inherited packet33 dispatch. The plan separately binds the
packet38 suite dispatch and its current CPU kernel gates. The actual suite
qualifies that combined dispatch. The qualification plan records this choice before launch;
export and seal bind both rank executables and every request to that identity.
GNU remains the compiler for native/Python equivalence and request-order proof.
Compiler choice here makes no model-speed claim. Coordinator WS
uses the current full suite manifest separately, as documented in `WINDOW.md`.

After every required gate is current, finalization is deliberately three steps:

```bash
packet38_cpu "$packet38/seal.py" --bootstrap
packet38_cpu "$packet38/test_window_seal_admission.py" --build-receipt "$packet38/build-admission-candidate.json"
packet38_cpu "$packet38/seal.py"
packet38_cpu "$packet38/cleanup.py"
```

The bootstrap writes only an admission candidate, never `build-receipt.json`.
The admission rehearsal blocks every launcher and checks all window consumers
on CPU. Final sealing requires that rehearsal and rechecks its source/contract
hashes, all gate receipts, binary identities, precision flags on compile and
link, captured inputs, real-controller signatures and archived suite warm-up.
Cleanup preserves sealed coordinator inputs and binaries while archiving and
removing disposable scratch. Every large write must first pass the 8 GB root
reserve and 3 GB build-tree admission.
