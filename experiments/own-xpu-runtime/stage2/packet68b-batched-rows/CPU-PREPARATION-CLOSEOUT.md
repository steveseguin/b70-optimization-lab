# Packet 68b CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Prepare a shared-weight M=2 target-half probe without changing each row's
`iq3-p49-split32-v1` arithmetic. October 17, 2026; packet64 production draft,
ordinary rollback, 24/24 layers, intended lane B on two B70 cards. Preparation
was CPU-only on steve-b70s. Commit `9e33fe3ea` contains the sealed implementation.

## Outcome

CPU preparation accepted for a coordinator device screen. GNU and Intel
fixtures each pass 1,308 byte checks and agree across compilers. Native device
compilation and frozen-wrapper plan admission pass. No device measurement,
13-request oracle pass, or performance qualification is claimed.

## What worked

Dense projections and target HC share decoded weights between separately
ordered row accumulators. Packed IQ2 gate/up and IQ4 down use a stable union
of routes. Tests include different, repeated, partial and invalid routes,
nonfinite inputs, inactive controls and context limits. The analyzer's two
CPU tests pass: pipeline reward/rejection accounting and rejection of missing
or failed device evidence. These are small fixtures, not CPU model runs.

## What failed or remains uncertain

The initial CPU plan used an output directory outside the frozen supervisor's
allowed evidence root. Its rejected plan/seal remain under `evidence/unadmitted-*`;
the corrected plan is admitted. No GPU was contacted.

GDN recurrence, conv, QSA attention cores and remaining unsupported classes
still execute serial production row operations. Duplicate independent rows
maximize expert overlap and do not prove a causal consecutive-row verifier.
Actual H(2)/H(1), device byte identity, all thirteen packet49 streams and the
+8% projection decision await the coordinator. Restore cost also needs measured
packet68 evidence; the analyzer labels an absent cost as a sensitivity only.

## Evidence and patches

- [CPU byte gate](fixture/receipt.json) and [retained gate evidence](evidence/cpu-gates.json).
- [Device build receipt](build-device-receipt.json), [seal](screen-seal.json)
  and [admitted plan](evidence/probe-plan.json).
- [Commands, scope and retention instructions](README.md).
- [Analysis tests](test_analysis.py) and [analysis helper](analyze_probe.py).
- [Task note](../../../../notes/2026-10-17-own-runtime-packet68b.md).

The ignored local build is required by the seal and remains available for the
coordinator. Temporary analysis fixtures were removed automatically. The
original packet64 tree and all other frozen trees were left unchanged.

## When to revisit

Run the sealed coordinator window once under its admitted unit, then analyze
the exact receipts. Use measured class ratios to choose the next batching
lever. A failed identity gate requires a new preserved variant, not an edit
to this sealed source. No automatic retry or service restoration is supplied.
