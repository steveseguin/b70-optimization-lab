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
