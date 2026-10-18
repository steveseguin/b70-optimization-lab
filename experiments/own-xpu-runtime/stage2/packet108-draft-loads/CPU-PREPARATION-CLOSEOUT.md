# Packet108 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can the unchanged mtp36 draft INT8 operator benefit from eight-value loads
without packet59's scheduling/fusion changes? This preparation copies packet103
for the Flash-Next UD-IQ3_XXS compressed-model lane, targeting the existing
`iq3-p49-split32-v1` target oracle. The proposed diagnostic uses one B70 on
lane B, full expert shapes and packet100b target-route replay. Date: October 18.

## Outcome

The micro compiles and its temporary queue plan passes. No device executed.
No performance or exactness candidate has qualified or failed. Integration
remains conditional on the complete 15% device micro gate; this closeout covers
CPU preparation, not a speed verdict or the end of the optimization lane.

## What worked

Existing command receipts support a fresh hit/miss dependency budget. Missing
per-class device events stay explicit. The micro holds weight layout, WG128,
SG32, reduction order and stores constant while changing only raw loads.
Thirteen analyzer tests reject missing/inexact/incorrect-order evidence and
weak individual strata, even when the overall median looks good.

## What failed or remains uncertain

No fresh per-kernel p97+tile16 GPU attribution exists in the supplied receipts.
The compiler waited for the whole-host hold and then completed; it did not
interrupt the record work. A compiler could already combine production loads,
so the change may save nothing. Captured target IDs are only a proxy for draft
routing. Current operator time, device byte identity, true native-route model
transfer, startup gates and quality/record qualification are all unmeasured.

## Evidence and patches

- [Budget and ranked levers](../packet108-attribution/BUDGET.md), with the
  [reproducible, hash-bound extraction](../packet108-attribution/budget.json).
- [Source origin](source-origin.json), copied `mtp_kernels.cpp`,
  [baseline](p108_base.hpp), [candidate](p108_loads.hpp) and derivation scripts.
- [CPU compilation receipt](evidence/microbench-build.json) and
  [temporary queue plan](evidence/queue-plan.json).
- [Micro method and conditional next gates](README.md).

Generated build files stay ignored. Restore with `build_microbench.py` on
the same compiler path using the documented nice/affinity/closed-stdin limits;
it rebuilds the checked include mirror and binary. Existing build logs refuse
overwrite: use a new build directory or preserve the old log before rebuilding
this packet's own generated build. No frozen parent is a cleanup target.
The 46,080-byte route payload and compressed provenance manifest are retained
locally in `evidence/`; input provenance remains individually hash-checked.
No new retained artifact reaches 1 MiB.

## When to revisit

The coordinator may run the new micro proposal after normal lane admission.
A complete arm must save at least 15% in every stratum and both orders.
Only then run repeated GNU/Intel byte gates, every real chain-window startup
and host-reference path, full-size memory admission and seals, followed by
B grid and matching A confirmation. A micro loss closes this load-only arm.
