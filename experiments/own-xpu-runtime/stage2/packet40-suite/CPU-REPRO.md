# CPU preparation and final sealing

Run from the repository root with the inherited CPU affinity. These commands
never execute a device program. At most two compilation jobs and four CPU-bound
processes are permitted; the simplest reproduction is serial. Every Python
invocation uses `-B`. The packet requires NumPy in the lab Python environment,
GNU C++, Intel oneAPI 2026.0, the pinned local target input files, and the official
draft shards listed by `official-tensors.json`. No download is implicit.

```bash
set -e
packet40=experiments/own-xpu-runtime/stage2/packet40-suite
packet40_python=/home/steve/.venvs/vllm-xpu/bin/python
packet40_cpu() {
  nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 "$packet40_python" -B "$@"
}
packet40_cpu "$packet40/build.py" prepare
packet40_cpu "$packet40/build.py" gnu-host
packet40_cpu "$packet40/build.py" icpx-host
packet40_cpu "$packet40/build.py" asan
packet40_cpu "$packet40/build.py" device
packet40_cpu "$packet40/build_native_controller.py"
packet40_cpu "$packet40/seal40.py" --record-phase cheap -- "$packet40_python" -B "$packet40/cpu_campaign.py" cheap
packet40_cpu "$packet40/seal40.py" --record-phase mini -- "$packet40_python" -B "$packet40/cpu_campaign.py" mini
packet40_cpu "$packet40/seal40.py" --record-phase real-gnu -- "$packet40_python" -B "$packet40/cpu_campaign.py" real-gnu
packet40_cpu "$packet40/seal40.py" --record-phase real-intel -- "$packet40_python" -B "$packet40/cpu_campaign.py" real-intel
packet40_cpu "$packet40/seal40.py" --record-phase real-native -- "$packet40_python" -B "$packet40/cpu_campaign.py" real-native
packet40_cpu "$packet40/seal40.py" --record-phase captures40 -- "$packet40_python" -B "$packet40/capture40.py" all
packet40_cpu "$packet40/seal40.py" --record-phase draft-auth -- "$packet40_python" -B "$packet40/draft_auth_gate.py"
packet40_cpu "$packet40/seal40.py" --record-phase draft-final -- "$packet40_python" -B "$packet40/cpu_campaign.py" draft-final
packet40_cpu "$packet40/seal40.py" --record-phase suite -- "$packet40_python" -B "$packet40/cpu_campaign.py" suite
```

These campaign phases reproduce the inherited parent gates and real-model
comparisons. Record every additional gate command with the same `seal40.py --record-phase PHASE -- COMMAND` pattern; final sealing rejects unrecorded or stale execution.

Additional inherited gates have their own named scripts and
source/binary-bound receipts: `native_controller_gate.py` for each normal and
sanitized controller binary, `native_mini_gate.py` without `--quick`,
`p38_kernel_gate.py`, `suite_gates.py`, `window_cpu_gate.py`, and the focused
`test_*.py` regression checks named in `cpu-tests.json`. The latter receipt is
the exact gate inventory; campaign completion alone cannot produce a seal.
`native_mini_gate.py` takes
`--binary "$packet40/build/gnu-host/own-rt-iq3"` and a fresh packet-local
`--output` path. Suite and window gates likewise accept fresh `--output` paths.
Archive completed gate scratch with `storage.discard` before the next stage.

The retained `suite-cpu-manifest.json` and `suite-cpu-freeze.json` pin the partial
real CPU suite. Do not silently substitute a growing live manifest into that
receipt. `cpu_campaign.py suite` runs this frozen snapshot in two persistent
Intel host ranks and archives it after exporting exactness evidence. Before
launch, all five Intel real-model mode receipts must pass with the current
binary and their inherited packet33 dispatch. The plan separately binds the
packet40 suite dispatch and its current CPU kernel gates. The actual suite
qualifies that combined dispatch. The qualification plan records this choice before launch;
export and seal bind both rank executables and every request to that identity.
GNU remains the compiler for native/Python equivalence and request-order proof.
Compiler choice here makes no model-speed claim. Coordinator WS
uses the current full suite manifest separately, as documented in `WINDOW.md`.

Packet40 also requires `capacity_gate.py`, `cancellation_retention_gate.py`,
`retention_caps_gate.py`, `draft_async_gate.py`, `full_wrapper_gate.py`, `python_tests.py` and the independent
reviews named by `qualification-checklist.json`. Record their exact commands and
receipts; a host-backend wrapper rehearsal is not a device gate.

After every required gate is current, bootstrap, rehearse admission, seal, then clean up:

```bash
packet40_cpu "$packet40/seal40.py" --bootstrap
packet40_cpu "$packet40/seal40.py" --record-phase seal-admission --receipt window-seal-admission-gates.json -- "$packet40_python" -B "$packet40/test_window_seal_admission.py" --build-receipt "$packet40/build-admission-candidate.json"
packet40_cpu "$packet40/seal40.py"
packet40_cpu "$packet40/cleanup.py"
```

The bootstrap writes only an admission candidate, never `build-receipt.json`.
The admission rehearsal blocks every launcher and checks all window consumers
on CPU. Final sealing requires that rehearsal and rechecks its source/contract
hashes, all gate receipts, binary identities, precision flags on compile and
link, captured inputs, real-controller signatures and archived suite warm-up.
Cleanup preserves sealed coordinator inputs and binaries while archiving and
removing disposable scratch. Every large write must first pass the 8 GB root
reserve and 3 GB build-tree admission.

Current selected-kernel captures use `capture40.py`, not the inherited
`capture_cpu.py`/`rebind_agreement.py` historical arithmetic comparison. Each
GNU capture is compared byte for byte with a fresh Intel host reference using
the same dispatch, then the CPU owner scratch is archived and removed.
`qualification_extra40.py native`, `p38k2`, and `integrity` reproduce standalone
sanitizer/controller coverage, K2 selection checks and input reauthentication.
`python_regression40.py` runs standalone regression producers that unittest
discovery cannot find. Record each command through `seal40.py`.

The additional `suite128_cpu_gate.py` gate uses the complete 128-token manifest
to select only `incident-retrospective`, once, on the Intel host backend with
native MTP and retention `1-8,97-104`. It requires 128 exact tokens and 768
fixture matches, then archives and deletes its scratch. Its scope is partial
1/12 CPU correctness, not twelve-prompt qualification or performance. Run it
through `seal40.py --record-phase suite128-tail --receipt
suite128-tail-cpu-gates.json -- COMMAND`; the command is the lab Python with
`-B` and `suite128_cpu_gate.py`. The resulting receipt determines whether this
additional gate has passed; this instruction does not assert its completion.
