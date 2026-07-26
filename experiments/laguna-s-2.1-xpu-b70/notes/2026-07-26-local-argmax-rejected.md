# Laguna — local-argmax draft reduction: rejected, and why the premise was wrong

Date: 2026-07-26 America/Toronto

## The candidate

`DFlashLagunaForCausalLM` did not inherit `LocalArgmaxMixin`, so the greedy
draft path all-gathered full vocabulary logits every cycle: 100352 tokens x 12
rows x 4 bytes = **4.82 MB**, against **768 bytes** for a (value, index)
exchange. A 6,272x reduction in bytes, on a TP4 group oneCCL reports as
PCIe-connected. The gap was real: the flag, the reduction and the mixin all
existed and only this model was not wired to them.

## Result: worse on both axes

| | control | local argmax |
| --- | ---: | ---: |
| scored median tok/s | **100.524890** | **97.937084** |
| bitwise exact vs q=1 | 13/13 | **12/13** |
| emitted per cycle | 3.9552 | 3.9546 |
| acceptance | 26.87% | 26.86% |
| derived cycle | 39.35 ms | **40.38 ms** |

**Rejected.** Slower by 2.6% and not exact.

## What the numbers say

Acceptance and emitted-per-cycle are unchanged to four significant figures, so
the reduction selects essentially the same draft tokens; it is not drafting
differently. The entire regression is **cycle time**, which rose 1.03 ms.

That refutes the premise. Moving 4.82 MB less data per cycle made the cycle
*slower*, so the collective on this group is not bandwidth-bound at these sizes.
Its cost is dominated by latency and by the per-call work around it, and the
local path adds a max, a stack, a view and a gather-and-argmax on top of a
collective that still pays a full round trip for 768 bytes.

**The generalisation worth keeping: on this PCIe-connected TP4 group, "send
fewer bytes" is not a lever at these message sizes.** Any future candidate whose
argument is byte reduction on a per-cycle collective should be expected to
disappoint unless it removes the collective entirely.

## The exactness failure

12/13, one prompt diverging. The tie-breaking equivalence argument -- each shard
takes its lowest local index, the cross-rank argmax takes the lowest rank, ranks
are ordered by vocab range -- was tested offline against a full-gather argmax
over 200 tie-heavy cases and held. It nevertheless diverged on hardware for one
prompt out of thirteen.

That was not chased, because the candidate is rejected on speed regardless. It
is recorded because the same 12/13 signature appeared at width 14, and a single
diverging prompt is invisible to any throughput-only comparison.

## Where this points instead

If the per-cycle collective is latency-bound rather than bandwidth-bound, then
the lever is the **number** of collectives, not their size. The audited topology
is 146 graphs and 145 eager breaks, made of **97 collective boundaries** (96
all-gathers plus one embedding all-reduce) and 48 attention boundaries, across
49 layers. That is roughly two collectives per layer, each paying a PCIe round
trip inside a 39.35 ms cycle.

Nothing here measures what one of those round trips costs, so this is a
direction rather than a claim. But it is the direction the local-argmax result
argues for, and it is the opposite of what was tried: fewer, larger collectives
rather than the same number of smaller ones.

It is also expensive and risky. Changing the collective count changes the
audited 146/145 topology, which is the invariant that has caught every
structural regression in this lane, including the one that took the host down.
Any attempt would need its own preregistration and a new audited count.

## Standing

Best measured result remains **100.524890** tok/s at width 12, 13/13 bitwise
exact. The mixin is committed but the flag defaults off, so the measured path is
unchanged.
