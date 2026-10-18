# Packet86 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Prepare a safe, explicitly non-exact limiter screen for the routed experts and
HC gates in a copy of packet75, with packet77 attribution. Same 24/24 target
placement and full BF16 KV; eight views, one binary. October 18, four-card host;
CPU only, with lane B proposed and equivalent lane A plans.

## Outcome

Preparation passed. All eight seals, sixteen full-shape startup/admission cases,
sixteen real lane plans, compiler/operator checks and eight Python tests pass.
Production CPU outputs match packet75. Diagnostic views intentionally differ.
No GPU time or achievable lossless speedup was measured.

## What worked

Explicit non-exact scope and real runner refusals keep these views out of
promotion. Separate load-retention controls make otherwise-dead weight reads
observable. Expected mismatches drain through the unchanged safety harness;
only the known post-release quality-report refusal is accepted as diagnostic.

## What failed or remains uncertain

An Intel initializer narrowing error, missing CPU-test OMP setting and JSONL
queue-collector assumption were corrected. Device runtime behavior, actual
cache residency, numerical stability of raw-byte outputs and all time savings
remain untested. Changed activations and routing confound the ablation bounds.

## Evidence and patches

[Final audit](evidence/final-check.json), [CPU identity](evidence/cpu-gates.json),
[operators](evidence/operators.json), [startup](evidence/fullshape.json),
[tests](evidence/python-tests.log), [queue plans](evidence/queue-plans.json),
[source identity](parent-source-manifest.json), [retention](RETENTION.md).

## When to revisit

Run the proposed lane-B screen only through coordinator admission and normal
fault/memory/drain checks. Analyze the signed site deltas before proposing any
new exact expert implementation. A later implementation still needs independent
quality and fresh-run performance gates; these diagnostics can never supply them.
