# Packet 21 fused launch schedule — CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can packet18's two-card chained decode schedule execute with at most 926
frozen / 876 R5 submissions per token while retaining arithmetic identity
`iq3-p17-detmath-v2`? Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS,
a quantized compressed model with its own exact oracle. Work dated 2026-10-11,
CPU only during FAULT HALT. [Source identities](source-provenance.json),
[preregistration](PREREGISTRATION.md), [build seal](build-receipt.json).

## Outcome

CPU implementation and qualification only. Frozen passes 64/64 tokens and
384/384 layer fixtures; R5 passes 8/8 tokens and 384/384 fixtures. Every generated
row in those complete gates records 876 compute submissions. Measured fusion-off
controls use 2,445 frozen / 2,181 R5 submissions. All randomized dependency gates
pass with zero violations, including the full 87-position prompt. Detailed gate totals
and measured control/per-layer submissions are in [README.md](README.md),
[cpu-tests.json](cpu-tests.json), [cpu-token-launches.json](cpu-token-launches.json)
and [launch-census-measured.json](launch-census-measured.json).
No device executed, no measured speed was produced, and no device-qualified
runtime or benchmark is promoted by this closeout.

## What worked

The sibling row table preserves matrix-specific decode and reduction trees.
Split4 executes its original partial and final tree inside one work-group.
Adjacent activation, BF16 stores and HC residual preserve rounding points.
Non-GEMV chains retain original group bodies with explicit phase barriers.
Sharded routing removes the repeated 2,560-wide gather; probability finishing
shares the expert launch without a cross-group data dependency.

[Independent arithmetic review](review-identity.md) and
[independent alias review](review-alias.md) found no unresolved defect in their
bound source. Fixture outputs match across GNU and Intel host compilers and
fresh processes; [fixture receipts](fixture-gates.json) include actual-adapter
coverage. Packet19's dependency checker retains access contracts, randomized
execution order and fail-closed unknown operations.

## What failed or remains uncertain

Two CPU attempts were stopped cooperatively before being counted: redundant
host prologue evaluation, then a final descriptor-validation change. Their
failed receipts remain recorded. The complete gates use the final runtime.
The first fixture attempt exposed duplicate allocation labels; the owner
correctly refused them. Intel host fixtures initially lacked the OpenMP loader
path. Both preparation defects were fixed before final repeats; neither was
reported as an arithmetic mismatch. [Negative-result index](DO-NOT-REPEAT.md).

Native arithmetic, queue behavior, JIT, longest submission and performance
remain unmeasured. A one-work-group chain can serialize substantial work.
Per-row HC prologue evaluation duplicates device work and consumes local
memory; mixed row variants leave some subgroups idle. These costs can offset
launch savings. Fixture coverage does not exhaust every NaN/Inf encoding or
all production shapes. A 30-us-per-launch estimate is only projected issue
cost, not token latency or throughput.

## Evidence and patches

All implementation changes, scripts, summaries and reviews live in this new
packet. Original packets13–20 remain read-only. [README.md](README.md) links
the complete gates and the per-site census. The ignored build directory holds
compiled binaries, manifests and sealed fixture inputs. Temporary run outputs
are removed after their hashes and comparisons are retained; rebuild with
`build.py --phase all`. Official/approved model bytes and the v2 oracle remain
at their existing local paths and are hash-bound rather than copied.

## When to revisit

After the owner's reboot/recovery and authorization, run the separately sealed
[K1/W0/W1/W2/W3 windows](WINDOW.md), respecting [submission budgets and watchdogs](DEADLINES.md).
Every wrapper refuses the current faulted boot. Failed windows never retry or
launch a successor. Native comparison must pass before any speed conclusion.
The next implementation lever is segmented replay under
[packet20's design](../packet20-launch/REPLAY.md), retaining dynamic state,
allocation ownership and explicit card-boundary fences. The lane remains open.
