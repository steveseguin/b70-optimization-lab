# Packet58e CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can the one-card chain share exactness windows with lane-B screens while
retaining the memory fence, 8 GiB reserve and existing drains, and use 90 s gaps?
October 17, 2026; copied frozen packet58d; card 0; target-only IQ3; BF16 KV;
`iq3-p49-split32-v1`. All 165 native source/constant files are unchanged.

## Outcome

CPU preparation passes. Exactness model admission starts at 85,565,068,816 bytes;
timing retains 118,308,908,048. Both serial builds, 70 Python checks, full
post-load allocation setup, reset checks and K1 bytes pass. No device ran.
Fit, complete measured post-load memory, device exactness and speed are pending.

## What worked

Full census backing plus observed shadow; clean reclaimable file pages excluded
from permanent exactness residency; unchanged live reserve and cooperative stop;
lane-A lease and WS128 hold-B; original shared teardown permit; 90 s gaps.
Temporary file-lock tests cover each window, timing waiting for B, exclusion,
stale markers, the actual adapter, exact card ownership and successful release.

## What failed or remains uncertain

58c has no successful after_load sample. Its 0.58 GB peak cannot replace full
cache/KV budgets. GPUActive is global; other-lane changes can mask or inflate its
delta, so complete census backing stays reserved independently. CPU tests found
old synthetic receipts lacking the new lane proof and publication-repeat guard;
fixtures were corrected. No device failure occurred during this preparation.

## Evidence and patches

[Allocation regression](evidence/postload-allocation-cpu.json),
[admission dry run](evidence/admission-cpu.json),
[Python tests](evidence/python-cpu-gates.json),
[queue plan](evidence/queue-plan.txt), [seal](build-receipt.json),
[native identity](evidence/native-unchanged58e.json) and
[frozen parent hashes](parent58d-source-manifest.json).
Historical raw receipts remain in their copied evidence directories and parents.
[Retention and restoration](ARTIFACT-RETENTION.md).

## When to revisit

The coordinator completes fresh `evidence/card0-58e-a`. Only a complete
measured census can support further budget reduction. A second whole-host
timing window is required for a speed verdict; shared-host WS128x is an
exactness repeat. This closes CPU preparation, not the optimization lane.
