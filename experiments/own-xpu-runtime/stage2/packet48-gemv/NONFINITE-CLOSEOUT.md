# Nonfinite weight-scale repacking — closeout

<!-- campaign-closeout -->

## Question and identity

Does the first packet48 compact-layout decoder preserve all NaN payload bytes
against the current packet45 arithmetic? October17 CPU-only tests on steve-b70s,
GNU g++ and Intel icpx2026.0, strict separate product/add, synthetic five-row
IQ2/IQ3/IQ4/Q6/Q8 fixtures. No model payload or device program was used.

## Outcome

Rejected for nonfinite weight scales. GNU's lane comparison selected
`0xffc00000` where the old path selected `0x7fc30000`. Intel's decoded IQ2
value selected `0x7fc00000` where the old path selected `0xffc00000`.
These are byte failures, not passes within a tolerance. No speed was measured.

## What worked

The revised loader boundary refuses every nonfinite scale before writing the
destination. Every FP16 NaN/infinity encoding and representative FP32 signed
infinities and signaling/quiet NaNs are rejected in the CPU unit gate.
Admitted finite scales, signed zeros, nonfinite inputs, lane sums and output
trees pass the revised strict gate under both compilers. The aligned compact
layout remains the candidate for the coordinator's device windows.

## What failed or remains uncertain

The unrestricted decoder's changed register/expression arrangement did not
preserve payload choice when arithmetic contained NaNs. Matching source
operation order alone did not prove that byte identity. The packet does not
claim device exactness even for its revised admitted domain. Future full-model
integration must check actual scales and retain the existing implementation for
an unsupported bank; this work did not scan the model to claim admission.

## Evidence and patches

[Failure receipt](evidence/nonfinite-rejected/failure.json), rejected
[header](evidence/nonfinite-rejected/gemv.hpp.txt),
[test](evidence/nonfinite-rejected/gemv_cpu_test.cpp.txt),
[GNU build identity](evidence/nonfinite-rejected/build-gnu.json.txt) and
[Intel build identity](evidence/nonfinite-rejected/build-intel.json.txt).
Original binaries remain locally in `build/nonfinite-gnu/` and
`build/nonfinite-intel/`; hashes are in those build identities. Their initial
stderr is retained verbatim in the failure receipt. No original bytes were
discarded or relabeled as a passing run.

To reconstruct the rejected unit test, copy the two `.txt` source snapshots
to a new directory under this packet's ignored `build/`, restoring their
`.hpp`/`.cpp` filenames. Use the corresponding receipt's `gemv_cpu_test.cpp`
compiler command with that new source and output path and add `-I` for this
packet directory; relative inherited headers then resolve without changing any
sealed source. Run the host test with nice19 and CPU4–15,20–31. No GPU binary
or model path is needed.

## When to revisit

Only when a real admitted model requires such scales, or an explicit original
payload-preserving fallback is designed and independently gated. Do not reopen
this issue by canonicalizing NaNs or weakening the byte gate. Continue the
finite-scale layout/M2 work through the coordinator's E1/E2 and T1/T2 windows.
