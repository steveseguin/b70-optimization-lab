# Exact expanded weights — CPU preparation closeout
<!-- campaign-closeout -->

## Question and identity

Can the separate Unsloth UD-IQ3_XXS target remove grid decode during GEMV
without changing a dequantized bit, while retaining the two-card budget?
October 11, 2026; own-runtime packet10; CPU preparation on steve-b70s,
coordinator device work restricted to card 3.

## Outcome

CPU operator preparation passes. Dense-only expansion fits the stated
arithmetic budget; full expansion and all-IQ2-expert expansion do not.
No device speed, native fit or complete-model quality result was obtained.

## What worked

Int8 values and cached exact FP32 subscales remove grid lookups and bit planes
from the device inner loop. The matching packed reduction remains the oracle.
[CPU receipt](build-receipt.json), [format and budget](README.md).

## What failed or remains uncertain

A new three-row MockDevice tail case caught a four-row upload into its
three-row allocation; the shared harness now uploads the bounded row count.
The [failed CPU receipt and repair](cpu-tail-repair.json) are retained.

The proposed signed nibble assumption is false for the direct IQ magnitudes.
FMA would change required rounding. The stored head is Q6_K, not F16.
The full expansion needs 157.954 GB of weights. Forecasts still trail 28.49
tok/s; actual device throughput, full-model parity and native fit are pending.

## Evidence and patches

[Expanded scalar/load contract](expanded.hpp), [kernels](kernels.cpp),
[Python oracle](expansion.py), [analysis](analysis.json), and
[device harness](tests/device_window.py) are retained. Validation removes only
its own ignored scratch; `validate.py --keep-build` recreates the inputs.
No historical device receipt or sibling file was removed.

## When to revisit

The coordinator runs the two hash-bound commands after card-3 admission.
Measure head SG32/split4 and complete representative GEMV sequences twice;
then integrate only after full-model exactness. Retain experts packed under
this budget and pursue their decode cost or dependency-correct small-op fusion
as the next lever if dense expansion alone cannot beat the reference.

## October 11 exactness repair follow-up

The first native gate failed on the IQ3_S format GEMV after 57 checks, with
clean teardown and no kernel faults. The original native error omitted row
and values; those cannot be recovered. CPU specialization reproduces row 23's
NaN sign flip, caused by conditional sign multiplication lowering to sign XOR.
The [repair and regression evidence](exactness-repair.json) and
[original device receipts](receipts-card3-exactness-20261011/card3-exactness/window.json)
are retained. Explicit cached NaN-bit propagation closes the proven CPU defect;
all eight format cases now exercise specialized GEMV against packed/materialized
oracles. Native mismatch reporting retains the first index and words.
The original latch remains; only the coordinator can qualify the repaired
kernel in a new admitted window. No GPU ran during this repair.
