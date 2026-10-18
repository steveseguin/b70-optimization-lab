# Packet58i one-card attribution — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet58g's frozen one-card target-only IQ3 receipts support an exact
placement/timing lever at least 10% faster than 24.34 tok/s, without exceeding
the original admitted host budget? CPU-only analysis, October 18, 2026 UTC;
48.6 GB pinned experts, 18 GB device cache, packet49 arithmetic and BF16 KV.

## Outcome

**No build; insufficient evidence for a qualifying prediction.** Existing
fill-DMA overlap models 26.11 tok/s under favorable assumptions, below 26.774.
Conditional extra cache models about 25.9 tok/s. Post-router copying could
exceed the bar, but unknown overlap and new synchronization move the estimate
to either side. No arithmetic, runtime, service or live state changed.

## What worked

All five windows' cache epochs reconcile with token receipts and cumulative
request counters. WS128's 1,188 metric positions average 7.835 ms cache wall,
65.46 MB fills and 93.124% inferred expert hits. Different expert sizes recover
layer 2's hit rate; independent calibration replay tests traffic changes.
Archived inputs and compact routes make the CPU calculations reproducible.

## What failed or remains uncertain

58g retained no route IDs, per-class device times, pure DMA times or per-layer
ordinary hit counters. Zero device fields mean disabled profiling. Cache wall
contains host work and waits; calling it all hideable PCIe time is invalid.
Tested LFU and frequency speculation lose on the proxy. Physical free VRAM
does not authorize increasing the original host admission.

## Evidence and patches

[Attribution and ranked hypotheses](ATTRIBUTION.md), [full JSON](ATTRIBUTION.json),
[models](lever-models.json), [route replay](route-replay.json),
[source snapshots](inputs.json), [verification](verification.json).
Only CPU analysis/replay code was written; no runtime patch or queue artifact.
The source snapshots preserve the exact bytes used, including untracked 58g
receipts. The route binding identifies the original packet55 inputs and the
validator used; compact routes retain exactly the values required for replay.

## When to revisit

A separately admitted, short one-card trace that separates host cache planning,
router readback, DMA/publication and resident gate/up duration, and retains
route IDs. Keep the original 118,308,908,048-byte whole-host budget, reserves,
BF16 KV and exactness requirements. Prove any reallocation before spending
unused bounds. This closes the CPU packet, not the one-card optimization lane.
