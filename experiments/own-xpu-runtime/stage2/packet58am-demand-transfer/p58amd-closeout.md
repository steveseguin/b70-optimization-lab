# Packet58amd mixed-layout dispatch repair — closeout

<!-- campaign-closeout -->

## Question and identity

Why did `bcs-demand-retained32x2` set the sticky software error on token 0 of
packet58an's S1, while S0 passed twelve prompts? Same mixed-quantization
UD-IQ3_XXS checkpoint, `iq3-p49-split32-v1` oracle, one B70 on lane A,
2026-10-19. This repair session performed CPU work only.

## Outcome

CPU-qualified repair; device confirmation pending. The old candidate forced
IQ2_S kernels onto layer 2's IQ3_XXS gate/up banks. The repaired dispatch keeps
that layer on unchanged parent kernels. There is no new speed or quality claim.

## What worked

The offline event trace shows substantial expert work through layer 2 and
skipped work thereafter. Its copy dependencies are ordered, with no packed
expert copies. The input manifest identifies the wrong layout at layer 2.
Real-plan preparation now captures 236 commands, versus the old 240, and
asserts that the four wrong layer-2 partition captures are absent. GNU and
Intel exact-byte tests, lookup/reset tests, and delayed-lease tests pass.

## What failed or remains uncertain

The first checked attempt stopped because a single request truncated the root
load-progress log. The harness now uses a one-row suite. Checked2 was revoked
unstarted when the dispatch defect was identified. GPU exactness, overlap,
overhead and speed of the repaired candidate remain unmeasured.

## Evidence and patches

- [Incident audit](evidence/p58amd-incident-audit.json) and [audit script](incident_audit.py).
- [Original incident](evidence/p58amd-original-incident/incident.json).
- [Dispatch repair](native/engine_demand.inc) and [type validation](native/demand_submit.inc).
- [Preparation regression](native/preparation_probe.inc) and [old-census negative control](test_layout.py).
- [Byte gates](evidence/bytes.json), [real-plan preparation](evidence/preparation.json), and [queue checks](evidence/p58an-checks.json).
- Previous active receipts remain in `lineage/p58amd-before/`; original raw
  device evidence remains under `screen/evidence/card0-demand-n/smoke/`.

## When to revisit

Coordinator admission of the fresh `packet58amd-demand-smoke-A` row must prove
exactness against the unchanged oracle. V5 remains conditional on successful
same-parent smoke and a refreshed measured storage reservation. No live queue
or service was started by this repair task.
