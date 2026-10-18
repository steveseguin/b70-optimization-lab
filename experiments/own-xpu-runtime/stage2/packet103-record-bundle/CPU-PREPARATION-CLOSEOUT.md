# Packet103 CPU preparation

<!-- campaign-closeout -->

## Question and identity

Prepare record bundle 5 from committed packet97e with packet100 tile16 DOWN and
packet101 split32 draft attention. Keep the iq3-p49-split32-v1 oracle, two-card
rank1 draft placement, 24/24 target layers and full 16-bit KV. CPU only.

## Outcome

Preparation is still running. Both binaries compile and all 512 factorized
operator products pass. All 1,024 real-size rank startup/allocation checks pass,
as do 529 synthetic submission cases. The final all-window source-bound startup
receipt, seals and temporary queue rehearsal remain pending. No device result
or speed improvement is claimed.

## What worked

The runtime selects every registered dimension in one binary per compiler.
Tile16 preserves the 360-byte DOWN row extent. Actual initialization/capture
checks cover new down dispatch, draft attention and all other choices together.
KD projects only unused target choices while preserving selected draft kernels.
Immutable parent metadata is copied locally. The submission fix and placement
and new-dimension disclosure are present before sealing.

## What failed or remains uncertain

The inherited K2 regression retained over 1 GB of temporary copies across 512
cases. It now removes each case after checking it. The first startup pass’s 357
successful compositions are retained as diagnostic history; a full repeat binds
the corrected sources. Draft split32 matches its own fixed reference; it is not
a claim of parity with the old draft reduction. Full target-model equality,
acceptance, repeats and speed remain device gates. A conservative disk refusal
was recorded and must pass before launch.

## Evidence and patches

- [Build](build-device-receipt.json), [operator bytes](evidence/cpu-byte-identity.json)
  and [arena admission](evidence/full-shape.json).
- [Submission replay](evidence/submission-tests.log) and
  [bounded dispatch regression](evidence/bounded-dispatch-test.log).
- [Packet103 work note](../../../../notes/2026-10-18-own-runtime-packet103.md).
- [Orchestration](../../ops/packet103-orchestration/README.md).
- [Original-copy identities and historical archives](copy-lineage.json).

## When to revisit

Before device launch, require current source qualification, no later lane-A
veto, matching composite brackets, unchanged oracle output/acceptance, current
storage admission and a fresh chain folder. Any covered startup source change
requires the full source-bound CPU gate again. Do not edit sealed consumers
after a chain; create a new descendant with its own gates instead.
