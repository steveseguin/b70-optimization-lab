# Packet64 attribution selection

CPU preparation is complete. This is an instrumented copy of packet64's
engine: HC fusion, spin waits, 24/24 target layers, rank-1 production draft,
91,392-row draft head, ordinary rollback copies, and unchanged BF16 KV.
Packet49 remains the target oracle. Device costs are **not measured yet**.

The fixed selection is `selections/1-production-control`. It uses the new
[`screen/v3-attr`](../screen/v3-attr/README.md) wrapper. The frozen packet64
screens cannot admit this new placement lineage without edits, so this wrapper
copies the lane-aware companion and preserves its shared hold/drain protocol.
Neither frozen engine nor frozen wrapper was changed.

One load runs an incident64 check, all twelve 128-token control requests, then
all twelve 128-token instrumented requests. Every request resets mutable state
and checks every target token against packet49. RESET's otherwise-unused token
field switches observation off/on; it changes no numerical state or kernels.
This is repeated-prompt diagnostic work, never eligible as a speed record.

Packet57's event recorder observes generated indices **9–16** at existing
drains. It records the full draft, transfers, and representative target layers:

| Rank | GDN | QSA | Whole target-layer span |
| --- | ---: | ---: | --- |
| 0 | 22 | 23 | first kernel of layer 0 through last kernel of layer 23 |
| 1 | 24 | 27 | first kernel of layer 24 through last kernel of layer 47 |

The extra span endpoints do not add kernels or waits. The summarizer reports
class microseconds per complete layer/type/rank, draft classes, both rank half
times, rank finish balance, and outside-layer duration. Outside-layer duration
is the host half-command duration minus its same-card target-layer device span;
it includes preparation, snapshots, final head and handoff outside that span.
It is **not GPU idle**. Cancelled or incomplete spans are excluded. Negative
residuals remain visible.

Raw event times and the paired control ratios are retained separately. Scaling
target costs by the control/instrumented cycle ratio, scaling draft by its wall
ratio, and multiplying sampled classes by 18 GDN + 6 QSA per half all produce
**estimates**. Fused kernels remain attributed to their surviving launch labels.
The ranked lever table contains cost buckets, not additive speedup promises.

Expected device work is **about 10 minutes**, including a single load and
teardown, based on the existing screen estimate plus a second suite. This is
not a measured duration and excludes lane-hold/admission waits. The inherited
one-hour cooperative watchdog is a stop bound. The coordinator owns the run.

[Exact commands](WINDOW.md), [CPU closeout](CPU-PREPARATION-CLOSEOUT.md),
[boundaries](DO-NOT-REPEAT.md), [retention and rebuild](RETENTION.md),
[task note](../../../../notes/2026-10-17-own-runtime-packet64-attribution.md).
