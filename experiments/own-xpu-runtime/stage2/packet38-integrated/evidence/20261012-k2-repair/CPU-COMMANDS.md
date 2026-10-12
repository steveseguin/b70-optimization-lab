# Focused CPU rebuild and checks

From the repository root, with the existing admitted compiler environment and
unchanged CPU affinity. Each build uses two compile jobs; run these sequentially.
`repair_build.py` regenerates objects removed by the previous cleanup, compares
unchanged object bytes and ordered link commands, then removes only those
regenerable objects after recording their hashes. No device program is executed.

```bash
packet38=experiments/own-xpu-runtime/stage2/packet38-integrated
nice -n 19 ionice -c 3 df -B1 /
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/repair_build.py" gnu-host
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/repair_build.py" icpx-host
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/repair_build.py" asan
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/repair_build.py" device
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/repair_gates.py" unit
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/repair_gates.py" resident
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/entry_codes.py"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/validation_gate.py"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/fixture_gate.py"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/p33_linked_fixture_gate.py"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/window_cpu_gate.py" --phase fixtures --skip-wrapper-tests --output "$packet38/build/repair-window-fixtures"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/window_cpu_gate.py" --phase models --output "$packet38/build/repair-window-models"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/test_window_storage.py" --output "$packet38/review-resume-window-storage-gates.json"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/test_draft_window_cleanup.py"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/test_seal_bootstrap.py"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/seal.py" --bootstrap
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/test_window_seal_admission.py" --build-receipt "$packet38/build-admission-candidate.json"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/seal.py"
```

The repair's temporary window/linked outputs were archived with the packet's
byte-verifying `storage.discard` helper after their gates passed; receipts are
in this folder. Choose unused window output names if reproducing before that
cleanup. Build receipts record the exact expanded compilation commands and
elapsed time. The build used packet-local `build/tmp` as TMPDIR.
