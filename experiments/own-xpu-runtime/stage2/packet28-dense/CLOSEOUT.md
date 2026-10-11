# Packet28 CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can shape/format-specific kernels remove redundant per-weight GEMV work while keeping
`iq3-p17-detmath-v2`? Target: the IQ3 quantized compressed model in model-tensors.tsv,
packet26 R5 runtime dispatch, Intel Arc Pro B70. Prepared on steve-b70s,2026-10-11;
CPU only. No model weights were downloaded or changed.

## Outcome

CPU preparation passes the recorded finite-bit/NaN-category gates and builds the native
program. No device ran; no speed or candidate dispatch is admitted. Full exceptional
bit identity is pending: host compilers choose different payloads in mixed-NaN sums.
Native G2 keeps strict new/current byte equality including NaNs.

## What worked

Scale loads once per lane tile, byte grid tables, separate paired accumulators and
compile-time format/shape families pass the CPU arithmetic tests. Direct packet26
R5 calls avoid packet25's unrepresentative baseline. Explicit event grouping counts
both stages of single-subgroup split4. Nothing is yet qualified for runtime promotion.

## What failed or remains uncertain

Mixed-NaN payload identity is not certified. Register/launch choices may be slower;
the48.1/21.9/71.2us bounds are hypotheses, not packet28 measurements. Each baseline
must reproduce its in-model cost within15% before its candidate can be adopted.
Real model v2 CPU-oracle parity, repeated native owners, kernel JIT and performance
remain pending. No CPU clock is used as GPU performance evidence.

## Evidence and patches

[Build receipt](build-receipt.json), [CPU gates](cpu-tests.json),
[fixture archive](cpu-harness-evidence.json.gz), [compiler logs](compile-logs.json.gz),
[independent dense review](review-dense.md), [expert review](review-experts.md),
[bridge review](review-bridge.md), [admission review](review-admission.md),
[new dense source](dense.hpp), [expert source](expert.hpp), [submit bridge](submit.cpp),
[prepared harness](g2.cpp), [operation counts](README.md).
Scratch is removed after archiving; ignored sealed executables remain for the owner.
Reconstruction commands and source/flag/binary hashes are retained. Protected source
packets and the active packet27 tree were not edited.

## When to revisit

Run [K0 then G2](WINDOW.md) after coordinator card admission, then follow
[INTEGRATE.md](INTEGRATE.md) for K1/K2 and full model/fresh-owner oracle gates.
[DO-NOT-REPEAT.md](DO-NOT-REPEAT.md) records closed arms and their revisit conditions.
This closes preparation, not the optimisation lane.
