# Packet64 attribution CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can the current packet64 24/24 production-draft engine expose in-engine class,
rank-half, outside-layer and draft costs in a short lane-B diagnostic? This
copies the Unsloth IQ3 compressed-model runtime with packet64's target HC fusion
and spin waits, unchanged packet49 target oracle, production draft and BF16 KV.
All work on October 17 was CPU only on steve-b70s.

## Outcome

Prepared and sealed, with no measured device result. Four fresh host processes
match packet64's 96 target fixtures, 24 tokens, draft proposals and draft state.
Three additional requests on one host-only pair match while toggling observation.
Both builds, 90 wrapper tests, five report tests, both seals and lane-B plan pass.
See [validation](cpu-validation.json), [CPU gates](evidence/cpu-gates.json),
[reset gate](evidence/reset-gate.json), [report tests](evidence/attribution-tests.log),
[wrapper tests](../screen/v3-attr/placement-validation/cpu-tests.log).

## What worked

Packet57's recorder ports onto packet64 without arithmetic changes. New target
samples follow the 24/24 ownership, and endpoint events measure complete layer
spans without new kernels or barriers. A sealed RESET observation flag allows
both full-suite arms to share one load. The copied lane-aware wrapper keeps the
whole-host speed-window hold and shared drain spacing.

## What failed or remains uncertain

The initial mechanical port needed the packet64 rank0 profiling predicate
preserved explicitly. The initial sparse-only design was extended with direct
layer-span endpoints before the final build. Final CPU fixtures pass again.
No GPU fault or device launch occurred. The true event inventories, cancellation
coverage, profiling perturbation, actual runtime and safe live overlap still
need the coordinator's run. Fixed arm order and possible lane-A overlap are
confounders; estimates cannot become headline measurements.

## Evidence and patches

[Final source delta](packet64-attribution.patch),
[selection seal](selections/1-production-control/screen-seal.json),
[plan](evidence/plan-B.json), [build receipt](build-device-receipt.json),
[object identity](evidence/object-identity.json), [retention](RETENTION.md),
[task note](../../../../notes/2026-10-17-own-runtime-packet64-attribution.md).
Build binaries/logs and synthetic raw fixtures remain in the ignored local
`build/`; compact hashes and exact fixture records are tracked. No real-model
attribution output exists yet.

## When to revisit

The coordinator runs [the fresh lane-B screen](WINDOW.md) after normal admission.
Its retained report ranks the next lever. Any new placement, draft choice or
miss-copy mode requires a new sealed selection; the existing frozen packets and
queued chains must stay untouched.
