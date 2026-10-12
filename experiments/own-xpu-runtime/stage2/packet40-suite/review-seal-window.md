# Seal and window source review

The requested window/controller matrix is present, and deadline values agree with the wrapper and satisfy the minimum watchdog rule. This review ran no rank or device. Seven isolated seal/warmup mock checks passed; actual final seal and complete wrapper admission rehearsal remain pending.

Two source gaps were fixed with parent authorization. First, `seal.py --bootstrap` writes only `build-admission-candidate.json`, preserving final build receipt, CPU test summary and binary hash document. A default final seal requires the admission gate and verifies its source hashes and exact consumed seal contract. The CPU admission test can inject a candidate only inside its mocks; no production wrapper candidate option or bypass was added.

Second, the seal now validates the archived excluded warmup against hash-bound input snapshots. It requires the selected synthetic five-token sequence, two completed outputs, token hash, EOS suppression limited to warmup and the complete-reset assertion. A prior first-prompt warmup receipt cannot satisfy the new check. The final seal records the warmup receipt hash.

The parent is updating the command documentation to archive a completed W2 controller pair after parity comparison, keeping required K/KD/capture evidence available. Retaining every pair under build would otherwise eventually trigger the 3GB refusal.

After actual CPU gates complete, use:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet38-integrated/seal.py --bootstrap
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet38-integrated/test_window_seal_admission.py --build-receipt experiments/own-xpu-runtime/stage2/packet38-integrated/build-admission-candidate.json
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet38-integrated/seal.py
```

These commands are prepared instructions, not a claim that the seal or admission gate ran.

## Intel CPU suite qualification decision, before launch

The parent authorized selecting the separately qualified Intel host executable for the persistent real CPU suite to reduce qualification time. This is a scheduling decision, not an inferred model speedup. The suite remains pending. GNU continues to own native-mini equivalence, request-order proofs, all five native real-controller comparisons, and captures. No runtime/C++/suite execution path was changed by this decision.

The campaign now requires all five Intel modes to pass against the current binary and dispatch before recording `suite-cpu-qualification-plan.json` and launching. The export verifies both rank executable paths and every request's binary hash; it records the compiler and executable. The seal binds this suite to a separate Intel hash and preserves the GNU identity of all other checks. Nine synthetic prerequisite checks, nine export/retention checks and seven seal/warmup mocks passed without launching ranks. Actual persistent Intel suite evidence remains required.

The first suite preflight correctly refused before any rank launch, but its expected dispatch was wrong: Intel real-mode prerequisites ran under `dispatch-p33.json`, while the intended suite uses `dispatch-p38.json`. The corrected plan records `prerequisite_dispatch_sha256` and `suite_dispatch_sha256` separately. Admission also verifies current p38 kernel source/binary/child receipts and the dual-compiler full-array capacity gate. A read-only check against all five actual Intel receipts now passes, recorded in `suite-compiler-admission-check.json`; this is not suite execution. Ten prerequisite mocks, nine export checks and seven seal mocks passed after correction.
