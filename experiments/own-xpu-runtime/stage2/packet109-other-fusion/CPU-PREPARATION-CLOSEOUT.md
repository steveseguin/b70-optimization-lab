# Packet109 CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Question: can exact shape-specific epilogues remove small-operation launches
from both halves of the packet103 selected target without changing arithmetic?
Identity: copied packet103 sources and selected layout, `iq3-p49-split32-v1`,
BF16 KV, fixed split32 draft, other_fusion production versus fused.

## Outcome

The census and implementation remove 72 launches per half. Device quality and
complete-engine performance remain unmeasured.

## What worked

The route/shared
activation and shared-down/mixture/blend fusions preserve their intermediate
outputs and arithmetic order. Per-compiler byte gates cover admitted nonfinite
inputs; the first two NaN expression variants failed and remain retained under
`evidence/rejected-v1` and `evidence/rejected-v2`. They are not selectable.

## What failed or remains uncertain

The early NaN expression failures require per-compiler, final-flag checks and
the actual production runtime-shape compilation boundary. Final GNU CPU blend
uses that original complete loop; Intel tests the fused per-row device source.
Packet100 correctly refuses the small synthetic reset model; those orchestration
tests explicitly project only the expert layout to wide64. The real selected
expert layout is exercised by full-shape and all-window startup gates.

## Evidence and patches

CPU preparation gates are recorded under [evidence/](evidence/full-shape.json);
see the [source overlay](native-overlay.patch), [byte fixture](fusion_cpu.cpp),
[census](CENSUS.md) and [retention instructions](RETENTION.md).
Native and wrapper seals
bind the final reports, source and binary. The full-shape fixture checks both
ranks, all five views and fresh candidate capture equality. Startup109 exercises
all eleven chain windows. Exact CPU byte checks are repeated with GNU and Intel.
The reset and IPC fixtures exercise real native lifecycle paths but use small
synthetic models and cannot qualify device model quality.

## When to revisit

No device result exists. The proposed lane B one-load A/B/A/B/A screen is the
next decision point: exact tokens first, then complete-engine timing. The
launch saving estimate is only a hypothesis. Revisit or split a fusion if the
device oracle fails or complete-engine timing regresses; never promote a CPU
fixture or launch-count reduction as model throughput.
