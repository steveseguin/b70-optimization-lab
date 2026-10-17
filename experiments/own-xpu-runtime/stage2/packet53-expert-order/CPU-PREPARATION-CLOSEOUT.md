# Packet53 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Prepare eight expert-only scheduling candidates for the lab's Flash-Next
UD-IQ3_XXS runtime, preserving packet48b production arithmetic and packet49
oracles. Fixed shapes are IQ2_S paired gate/up K2560 and IQ4_NL down K640,
ten routed experts, M1 and two serial rows for M2. Device qualification is
reserved for coordinator-owned B70 card0, PCI0000:23:00.0.

## Outcome

CPU preparation passed. Four fresh GNU/Intel proof runs each pass 8,432,381
checks over 2,250 sampled rows with the same receipt/output hash. Two complete
host runs each pass all 60 production-shape comparisons, including M2, with
identical captured output/state hashes. One AddressSanitizer/UBSan proof passes
with the same hash. All 17 mocked wrapper/parser tests and all three builds
pass. Device compilation is not device execution; E1/E2/T1/T2 remain pending.

## What worked

The independently written scalar decode/FP32-chain/tree proof verifies
virtualization before BF16 rounding. Scheduling census covers real and padded
counts. Production controls, route/status/error captures and the common
30us two-owner selection are bound from the beginning. The PF_EXITING sensor
and past-UTC fault-review refusal carry packet52's corrected supervision.

## What failed or remains uncertain

Two proof-fixture bugs were corrected with rejected sources retained: reuse
of a lane array modified by the production tree helper, and compiler-dependent
evaluation order of two RNG calls. Intel's expected one-thread warning is
recognized without relaxing the thread cap or hash checks. No arithmetic
failure was waived. SLM bank conflicts, register use, native shuffles,
full-model integration and device performance are unmeasured.

## Evidence and patches

[CPU gates](cpu-gates.json), [Python gates](python-gates.json),
[independent review](REVIEW.md), [cleanup](cleanup.json),
[initial proof refusal](evidence-cpu/initial-proof-refusal/README.md),
[second fixture refusal](evidence-cpu/second-proof-fixture-refusal/README.md).
All source remains in this packet. The build peaked at 67,184,847 bytes;
cleanup removed 6,976,241 bytes of own regenerable scratch and retained
60,208,606 bytes. No other packet's builds or chain files were touched.
[CPU-BUILD.md](CPU-BUILD.md) regenerates the deleted compiler scratch.

## When to revisit

The coordinator runs the sealed [E1/E2/T1/T2 commands](WINDOW.md), after current
GPU ownership is released. Timing waits for two fresh production-byte passes.
Require one common selection saving at least 30us in each fresh timing owner;
report all arms and M2 independently. A passing operator screen still needs
an explicit integration packet and existing-oracle model checks. No oracle
or runtime server is launched by this preparation.
