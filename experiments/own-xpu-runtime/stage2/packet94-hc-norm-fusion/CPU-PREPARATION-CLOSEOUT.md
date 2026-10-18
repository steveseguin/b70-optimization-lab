# Packet94 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can the HC norm launch be removed by fusing its exact arithmetic into
low/injection? Packet84 copied bundle, quantized Flash-Next IQ3 lane, hc-wide,
ordered expert arithmetic, parallel recurrence, 24/24 target and rank1 draft.
Prepared on steve-b70s for B70 screening. Existing packet trees remain frozen.

## Outcome

CPU preparation passed for production, hc-normfuse and the downstream HC
weight-cache combination. All six full-shape device-startup mocks and memory
admissions pass. No GPU ran; device correctness and speed remain pending.

## What worked

The dedicated consumer keeps the original trees and BF16 boundaries. It
retains norm and scratch for their remaining readers while removing the
separate norm launch. Both compilers match every candidate output and scratch
byte to their production reference over four consecutive tokens, twice.
Three seals and both proposed screen directions pass CPU planning.

## What failed or remains uncertain

GNU and Intel production differ in existing NaN payload behavior; each
candidate matches its same-compiler reference without tolerance. The initial
cross-compiler assertion and raw receipts remain retained. Read-only review
found that startup archives needed explicit seal binding: seal.py now verifies
and binds all twelve native-plan/census archives. Extra norm recomputation may
offset launch savings; only matched device screens can establish the effect.

## Evidence and patches

[Exact chain and design](DESIGN.md), [byte checks](evidence/cpu-byte-identity.json),
[startup](evidence/full-shape.json), [memory](evidence/full-shape-admission.json),
[Python gates](evidence/python-tests.json), [review](evidence/read-only-review.md),
[final checks](evidence/final-check.json), [queue plans](evidence/queue-plans.json),
[retention and rebuild](ARTIFACT-RETENTION.md). The coordinator's whole-host
compile hold guard is preserved and included in every view seal.

## When to revisit

The coordinator chooses one direction from [WINDOW.md](WINDOW.md) and runs
its admitted grid. Only an exact improving winner with unchanged acceptance
counts advances to the other lane. Record-chain quality and performance gates
remain separate from these screens.
