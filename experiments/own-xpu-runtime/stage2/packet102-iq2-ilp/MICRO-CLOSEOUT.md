# Packet102 device micro gate closeout

<!-- campaign-closeout -->

## Question and identity

Does packet97 half-cache gate/up gain at least 15% lower kernel time from
batch2/4 lookup issue or shared activations? Full 640×2560 shapes, 512 experts,
ten selected experts, forty alternating pairs; `iq3-p49-split32-v1`.
The separate coordinator ran the early proposal on lane B during CPU preparation.
This task itself launched no device work.

## Outcome

All three device byte/status checks passed. No candidate passed the speed gate.
Batch2 took 98.11% of control time (1.89% lower); batch4 took 100.16%; shared
input took 103.31%. Both order halves failed the 85% threshold for every arm.
Six conditional screen proposals are retained but refuse execution. No model
speed result or record submission follows from this diagnostic.

## What worked

CPU GNU/Intel identity, linked assembly issue order, no spills for standalone
arms, and real full-shape startup all passed. The independently completed
micro drained and released its lane cleanly. The completed output refuses replay.

## What failed or remains uncertain

The intended load overlap and reduced activation loads do not provide the
registered kernel gain on this diagnostic. This is not a whole-model speed
verdict. B3 already failed its separate no-spill gate.

## Evidence and patches

[Qualification](evidence/micro-B/qualification.json),
[device window](evidence/micro-B/window.json),
[all samples](evidence/micro-B/samples.jsonl),
[CPU identity](evidence/cpu-byte-identity.json),
[lookup proof](evidence/lookup-issue-proof.json),
[kernel](p102_expert.hpp),
[coordinator note](../../../../notes/2026-10-18-own-runtime-packet102-result.md),
and [combined-arm closeout](COMBINED-CLOSEOUT.md).

## When to revisit

Require a materially different scheduling or state-lifetime design with a
credible larger effect. Do not repeat these same arms or relax the 15% gate.
