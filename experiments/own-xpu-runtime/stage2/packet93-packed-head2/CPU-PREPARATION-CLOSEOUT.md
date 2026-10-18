# Packet93 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can a genuinely new unpack mechanism make the packed Q6_K target head worth
screening? Packet84 copied bundle, quantized Flash-Next IQ3 lane with Q6_K
output.weight,248,320×2,560, rank1 draft/24+24 target, B70. Prepared October 18.
Packet74 sources and existing record trees are frozen.

## Outcome

CPU preparation passed. Two candidates are ready for an admitted single-card
microbenchmark, with a hard 15%-lower-time gate before either screen direction.
No device executed here; no candidate is adopted and speed remains unmeasured.

## What worked

GNU/Intel agree on exact decoded values, ordered reductions, logits and argmax.
All six full-size startup and VRAM checks pass. Offline assembly eliminates
some extra decode instructions; transposed storage removes alignment-repair
loads. Shared v4 plans and independent selection/threshold refusals pass.

## What failed or remains uncertain

Initial startup testing caught a test-only demangled-template spelling error;
it was corrected before sealing. The micro build needed the checked owner ABI
and its host handle helper; no device was involved. Review caught an inherited
false draft-sharing receipt, now fixed and tested. CPU gates cannot establish
device arithmetic, occupancy, bandwidth or speed. The strongest remaining
hypothesis is transposed storage; the word-plane arm keeps duplicated loads.

## Evidence and patches

[Diagnosis](DIAGNOSIS.md), [byte proof](evidence/cpu-byte-identity.json),
[startup](evidence/full-shape.json), [memory](evidence/full-shape-admission.json),
[Python tests](evidence/python-tests.json), [final plans](evidence/final-check.json),
[queue plans](evidence/queue-plans.json), [source identity](parent-source-manifest.json),
[retention/rebuild](ARTIFACT-RETENTION.md). Full raw CPU streams remain compressed;
no real model payload or token response was produced by this task.

## When to revisit

The coordinator runs the registered lane-B microbenchmark first. Only measured
qualifiers advance to one complete direction's matched engine brackets. A
candidate failing the micro gate closes without an engine launch. A winning
screen still needs separate record-chain quality and performance qualification.
