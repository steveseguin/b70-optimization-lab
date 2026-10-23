# Prefill storage and submission inventory

The [closed-run census](static-census.json), produced by
[planning_census.py](planning_census.py), bounds what the existing evidence can
tell us before implementing chunking. It pins the recorded plan, allocation
census, cache trace and fresh 370-token request traces. This is a static
inventory and recorded submission count, not a candidate measurement.

The first branch must use the current **expanded Q6** layout. Layer0 qkv is
21,504,000 logical bytes but 34,611,200 resident bytes (`expanded_sg32_v1`);
the z projection is 12,902,400 logical and 20,766,720 resident bytes under the
same variant. The output projection uses `expanded_split4_v1`. A test that
silently switches to packed Q6 arithmetic or another reduction tree does not
qualify the selected path.

The existing fresh request records 369 ordinary prefill positions, each with
1,110 kernel submissions, six host waits, three host-to-device copies and
50 device-to-host copies. The last prompt position is outside that count because
it computes the first generated token. Batching can potentially share dense
weight reads and reduce submissions or host boundaries, but these counts alone
do not price the saving. The logical plan's launch census includes sites that
the selected fused path combines; it must not replace observed submissions.

The timing trace has zero-valued device-time fields and no per-family enqueue
breakdown; the site trace is empty. Zero here means unmeasured, not free work.
The 2,863-row cache trace has aggregate fill/publication counters but no expert
route IDs. It therefore cannot measure adjacent-token expert overlap. Neither
the complete expert bank nor its resident cache is read in full each position.
Stored tensor sizes cannot be converted into a traffic or speed estimate.

The allocation inventory separates 295,612,132 bytes of device workspace,
59,019,280 bytes of recurrent state and 116,391,936 bytes of KV. These describe
the current engine. They are not an extra-row budget: shared persistent state
must stay shared, row-local temporaries need explicit lifetimes, and blindly
duplicating the large interpreter scratch is unnecessary. The first branch
proof establishes arithmetic and causality; complete workspace admission and
measured device benefit remain later gates.
