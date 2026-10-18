# Packet58ag CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can the remaining applicable bundle8 target refinements be expressed as
independent runtime choices in a frozen packet58ab one-card copy while
preserving `iq3-p49-split32-v1`, full BF16 KV and HC fusion? Prepared on
2026-10-18 on steve-b70s, CPU only, for card 0 with whole-host lane-A use.
The [audit](AUDIT.md) binds each historical mechanism and two-card gain.

## Outcome

CPU implementation and validation only. No one-card speed, physical fit or
full-model quality verdict is claimed. The first device milestone is the
unqueued 12 × 64 full-composition smoke; the five-view bracket follows only
after exact smoke completion. Final readiness is the separately sealed
`READY-FOR-DEVICE.json`, written after all retained checks and plans pass.

## What worked

HC-wide, wide64, exact half decoding, other-fusion and ordered foreground
retirement switch at a drained boundary without replacing allocations.
GNU/Intel byte tests preserve every compared intermediate/output/status byte.
The complete FP16 decode table preserves the packed weight layout. The
ordered-retirement port proves both foreground prefixes and leaves the
maintenance queue owned until its own drain. Baseline and composition both
retain HC fusion. Sparse real-shape checks preserve arena identities.

## What failed or remains uncertain

The new table exposed a missing upload slab in the CPU post-load fixture;
the fixture now includes and counts it. Intel's CPU retirement executable
initially lacked libiomp5 in its loader path; it uses the pinned launch path.
No GPU ran. Literal packet90 row expansion and two-card head splitting are
not portable to this unchanged one-card layout. Device bytes, stability,
fit and speed remain pending; historical two-card gains are not predictions.
Packet58r and 58t remain closed standalone arms.

## Evidence and patches

[Build](evidence/build.json), [HC bytes](evidence/hc-gates.json),
[port bytes](evidence/ports-gates.json), [retirement](evidence/retirement-gates.json),
[shape switching](evidence/fullshape-submit-cpu.json),
[reset](evidence/reset-gate.json), [entry/report](evidence/entry-gates.json),
[policy tests](evidence/python-cpu-gates.json) and
[temporary queue plans](evidence/queue-plans.json) retain the CPU receipts.
Source changes are in `sources/` and `native/`; the exact inherited closure,
original metadata and restore instructions are in `lineage/` and [README](README.md).
The oracle is a binding, not copied or regenerated model output. No model
weights or full raw model receipts were read for this preparation.

## When to revisit

The coordinator can admit the proposed smoke after the existing one-card
chain releases its whole-host hold. Require exact smoke output before the
combined bracket. The bracket's A0 remains exact but is warm-up for speed;
require both candidates to beat both warm controls by at least 2% with warm
control drift at most 3%. A failed device quality gate closes this composition
until localized, without changing the oracle or silently dropping a port.
