# Packet105 CPU implementation — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet87t's exact target-head row split be implemented on the frozen
packet97e source copy without changing iq3-p49-split32-v1 outputs or the draft?
The target keeps its Q6 head weights and BF16 row arithmetic. Rank1 owns
[0,202240); rank0 owns [202240,248320). October18 work is CPU only; two-card
B70 lane B and independent lane-A confirmation remain proposed.

## Outcome

The implementation and CPU checks pass. Three views are sealed and ten proposed
jobs pass temporary queue plans. No device result or measured speed gain is claimed. Packet87t's
+1.0685% is a prediction, not a measurement.

## What worked

Existing p33 row arithmetic and round2 selection can be reused unchanged with
partition-local extents and a global-index merge. The native controller has a
safe service point after rank0's speculative half and before its remote wait.
A separate copy-only queue can receive the current final.mix dependency while
rank1 submits the prefix head. The all-window CPU harness catches KD reference
startup defects that an ordinary model allocation check misses.

## What failed or remains uncertain

The first census caught a category/lifetime mismatch and unwanted private
scratch snapshots; both were fixed before any device launch. Dedicated BCS
availability, real queue overlap, driver residency, exact device output and
both lane speeds remain untested. Nonfinite diagnostic indices are not emitted
outputs; the gate checks raw logit bytes, finite argmax bytes and invalid-output
refusal. There is no permission to promote this CPU evidence as a GPU result.

## Evidence and patches

The implementation is in this directory, copied from packet97 after97e.
[Copy lineage](copy-lineage.json), [build receipt](build-device-receipt.json),
[CPU byte gate](evidence/cpu-byte-identity.json),
[allocation census](evidence/full-shape.json),
[actual-runtime mock](evidence/runtime-mock.json),
[native-controller mock](evidence/controller.json), and
[all-window receipt](startup97e.json) retain the identity and checks.
The [refusal checks](evidence/startup-refusals.json),
[guardrails](evidence/guardrails.json), and
[temporary queue plans](evidence/queue-plans.json) also pass.
The work note is [here](../../../../notes/2026-10-18-own-runtime-packet105.md).
Build objects are local caches, restored with build_engine.py using the pinned
packet97 object/source closure; no weights or binary caches are added to Git.
Retained compressed transcripts keep exact bytes from earlier CPU iterations.

## When to revisit

The coordinator may review the new proposed lane-B
and lane-A grids. Device execution requires its normal live fault and residency
admission. A winning lane-B placement still requires an independent lane-A
bracket and the existing full chain quality gates before any record claim.
