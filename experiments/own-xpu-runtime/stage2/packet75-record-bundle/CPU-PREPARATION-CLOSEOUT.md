# Packet75 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet70 record-chain code select packet74 packed head/dense kernels and
packet73 HC/expert kernels independently, without another merge build after
the screens finish? Tested October 17, 2026 on steve-b70s, CPU only. Target
arithmetic remains `iq3-p49-split32-v1`; packet49 is the device oracle.
The packet70 draft-HC, batch rollback, wide64 baseline and 24/24 placement stay
fixed. The shared v4-lanes wrapper is referenced under d5b060769 source hashes.

## Outcome

CPU preparation passed for all 24 choices in one merged binary. GNU and Intel
each passed two fresh byte comparisons per view: 96 executions, 90 cases each.
All 48 production-shape mock runs passed, including both ranks, actual row
strides, post-load allocation/capture and rank-one draft initialization.
Device exactness, deterministic repeats and performance remain pending.
No chain or service was launched. There is no packet75 speed claim.

## What worked

The dense/head selector composes with separate HC and expert selectors.
The full-shape mock executes the real initialization code with logical device
addresses and checked copy bounds. It confirms the 3,380-byte expanded head
stride and rejects a deliberately short packed-head allocation. Every window
plan calls the actual shared lane-admission predicate before returning.
The chain retains 90-second gaps. The shared screen wrapper releases its lease
before CPU report aggregation. Chain windows preserve packet70 ordering:
their initial reports precede release, and their final admission-bound receipt
follows completed drain and lease release.

## What failed or remains uncertain

Initial receipt finalization found a missing inherited RoPE link after the
build completed; exact source bytes and saved compiler output hashes allowed
receipt recovery without rebuilding or claiming an unrun check. The first
mock compile exposed duplicate owner declarations from using raw sources;
the test now uses the checked compiler mirror. A reporting-key collision was
fixed before the full sweep passed. Early inherited tests needed the current
record threshold and packet75 schemas; final tests pass. None of these CPU
fixes changes target arithmetic. The mock cannot establish device numerical
identity, device memory health, timing or a new record.

## Evidence and patches

- [Merged build receipt](build-device-receipt.json) and [parent source pins](parent-source-manifest.json).
- [Original operator fixture checks](evidence/cpu-byte-identity.json).
- [Per-view GNU/Intel byte checks](evidence/composed-byte-identity.json).
- [Full production-shape allocation checks](evidence/full-shape.json).
- [Chain and submission tests](evidence/chain-tests-v4.log).
- [All-view real window plans](evidence/all-view-plans.json).
- [Retained artifacts and rebuilding](RETENTION.md).

## When to revisit

Once each screen packet has a terminal decision, the preparation helper selects
only exact improvements confirmed by its own lane-A and lane-B rules. It
fast-reseals and writes readiness after all chain prechecks. The coordinator
then owns any separately authorized launch. A CPU pass cannot bypass the full
packet49 device oracle and registered record chain.
