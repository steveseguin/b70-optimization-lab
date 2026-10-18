# Packet67 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Which non-expert sites in packet64's `iq3-p49-split32-v1` target have useful-byte headroom, and can order-preserving candidates be prepared for the two-card B70 composition? October 17, 2026; header census and existing packet64 lane-B attribution only. No new model/device run.

## Outcome

Three sites have selectable candidates: attention HC gate, FFN HC gate, and GDN recurrence, plus a combined view and production. Host byte gates, submission/parser checks, offline device compilation and sealed lane plans pass. Device parity and performance remain unmeasured. No record changes or promotion.

## What worked

The audit accounts for expanded Q6/Q8 runtime storage and sums multi-stage calls. The HC geometry preserves finite reduction trees and uses the original exceptional arithmetic. A recurrence prepass removes repeated head normalization without changing state/output order. [CPU evidence](cpu-validation.json) binds the resulting choices and binary.

## What failed or remains uncertain

The initial HC virtual tree changed NaN payloads and was rejected. A duplicated sigmoid epilogue showed offline flag pressure and was replaced. CPU equality does not prove device subgroup equality; compiler spills, the recurrence extra launch, and weak microbenchmark transfer may erase gains. Outside-layer individual timings are absent, so their bandwidth/excess fields remain unknown. Draft activation/state accounting is incomplete and no full draft bandwidth is claimed.

## Evidence and patches

[Roofline](ROOFLINE.md), [HC source](p67_hc.hpp), [recurrence source](p67_recurrence.hpp), [failed source and receipt](evidence/failed-hc-virtualization.json), [negative index](DO-NOT-REPEAT.md), [build and retention](RETENTION.md), [screen plans and commands](WINDOW.md). Original frozen sources remain untouched.

## When to revisit

The coordinator runs the sealed A/B jobs. Reject any oracle mismatch before interpreting speed. Advance a promising composition to matched fresh-process quality and full realistic performance gates; if it fails, use the retained compiler evidence to decide the next mechanism.
