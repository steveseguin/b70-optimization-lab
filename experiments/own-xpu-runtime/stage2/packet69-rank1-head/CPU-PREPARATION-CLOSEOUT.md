# Packet69 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can rank1's outside-layer work be measured and screened for exact speedups?
October 17, 2026; packet64 production 24/24, rank1 draft, Unsloth UD-IQ3_XXS
Flash-Next target, 91,392-row prefix, full BF16 KV, packet49 oracle. CPU-only
preparation for coordinator-owned B70 lane screens.

## Outcome

CPU preparation passes; device outcome remains pending. The measurement view
and seven candidate views are sealed. There is no promoted speed or quality
result. Production stays default.

## What worked

The existing recorder omitted target head/final/argmax sites; the new filter
adds them without changing arithmetic. Wider head loads preserve every FP32
sum and BF16 byte in both host compilers. Independent row subgroups, split32
draft attention and draft HC have selectable views. Both wrappers release a
confirmed drained lane before CPU reporting. All sixteen quick plans pass.

## What failed or remains uncertain

Packed GGUF bytes understated the actual head traffic: the expanded draft
prefix is already about 561 GB/s at the raw measured time. Wider scheduling
may offer little; its two device screens decide. Draft attention arithmetic
changes may alter acceptance. Target head/final times cannot be recovered
from the old recorder. They await the new diagnostic window. No CPU model
qualification was run. Initial relocated-wrapper mock tests caught mismatched
receipt names and ownership-helper signatures; fixed before sealing.

## Evidence and patches

[Existing data](evidence/existing-analysis.json), [roofline](ROOFLINE.md),
[measurement command](WINDOW.md), [observer gate](evidence/observer-gate.json),
[candidate byte checks](candidates/evidence/cpu-gates.json),
[selection checks](candidates/evidence/selection-gate.json),
[quick plans/tests](screen/quick/validation.json), [retention](RETENTION.md).
Source copies and generated-build receipts retain exact parent identities;
raw packet64 device receipts remain in their original v3-attr evidence tree.

## When to revisit

The coordinator runs the sealed attribution window and both fixed quick jobs.
Use exact output, same-lane fresh controls and measured draft acceptance to
choose the next arm. A winner needs the full sealed chain; no CPU check here
permits a record submission. No existing frozen tree or GPU owner was changed.
