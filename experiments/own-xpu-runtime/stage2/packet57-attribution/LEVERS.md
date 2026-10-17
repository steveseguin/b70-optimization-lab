# Packet 57: pre-ranked levers

Ranking uses the [in-engine timeline](TIMELINE.md). Device attribution is
pending; no individual draft kernel has yet earned a speed claim or a place
ahead of another draft kernel. The packet 56 record is unchanged.

| Priority | Lever | Evidence now | Decision after the diagnostic |
| --- | --- | --- | --- |
| 1 | Remaining draft work: INT8 routed experts, attention, shared expert, HC/norms and embedding/merge | D is about 1.90 ms. Removing 0.5 ms or 1 ms from every draft has an idealized weighted-cycle benefit of about 1.87% or 3.82%; removing all D is an impossible 7.52% ceiling. | Rank the classes by observed event cost, host gaps and their contribution to D. Pursue a material combined saving while retaining exact arithmetic. |
| 2 | Target kernels that shorten both halves and the corrected rank-0 pass | Rank 0 finishes last in about 93% of complete cycles. The speculative half is about 16.15 ms on hits; the corrected half is about 14.76 ms on misses. | Compare representative GDN/QSA classes on both ranks. Rank by full-engine cost; account for the other half becoming the bottleneck. Do not reuse the earlier microbenchmark transfer assumption. |
| 3 | Miss-path scheduling and rollback work | Misses cost about 14.8 ms more than hits. Rollback itself is about 1.61 ms, with a much larger corrected target half after it. | Look for removable dependency or state-copy work, preserving exact rollback. Saving rollback alone has limited value; do not turn a tiny host gap into a campaign. |
| 4 | One-layer split rebalance | Average-half sensitivity predicts 22/26 about 0.11 ms slower per weighted cycle (roughly −0.53%); 24/24 about 0.83 ms slower (−3.75%). Actual migrated-layer costs are absent from the old receipts. | Use measured boundary layers 22/23 to replace the averages. Run a later split candidate only if the updated full-cycle calculation justifies it and memory fit is admitted. |
| 5 | Argmax/result-transfer scheduling | Rank 0 needs the proposed token before starting its speculative half. The existing asynchronous draft already overlaps other work. | Measure argmax, copies and publication separately. Only overlap work whose inputs are already available; do not count a causally impossible overlap as a saving. |
| Low priority | Move the draft to rank 0 without another scheduling change | Even an optimistic unchanged-cost placement sensitivity is about 0.41 ms slower (−1.86%): D and the rank-0 redo can no longer overlap on misses. | Revisit with measured placement costs or a new dependency-preserving schedule; moving the allocation alone is not supported. |

All percentages above are conditional weighted-cycle estimates on the retained
requests, not forecasts of the class-balanced leaderboard statistic. They hold
acceptance and target output fixed. The impossible remove-all-D case is a bound,
not an optimization proposal. Per-class event sums are not added to overlapping
wall intervals.

For 22/26, the model saves 0.13704 ms per cycle on correction but adds 0.24997 ms
to the parallel halves. With the same rank-0 removal assumptions, layer 22 must
cost less than **0.52526 ms on rank 1** to break even. Its old average-half proxy
is 0.63979 ms; neither number is a measured migration cost.

The draft experts are INT8 in production (`mtp.hpp`: `w.int8=routed&&!e.a.mini`).
The publisher's FP8 expert weights are requantized by the existing draft loader;
the full target verifier is unchanged. The target's packed-IQ kernel winners
therefore cannot be credited as draft-expert improvements.

## Fill from the coordinator's diagnostic receipts

| Measurement | Status |
| --- | --- |
| Draft attention, INT8 routed experts, shared expert, HC/norms, embedding/merge, prefix head, argmax and transfers | Pending device run |
| Target GDN/QSA class times on both ranks; boundary layers 22/23 | Pending device run |
| Control versus instrumented hit/miss cycle times and D | Pending device run |
| Raw class costs and explicitly labeled perturbation-scaled sensitivities | Pending device run |
| Exact target tokens against packet 49 oracle in both arms | Pending device run |

Keep negative results and failed quality checks. This diagnostic is not a
performance submission, and a short event sample does not establish a speed
verdict. Any later candidate still needs its own unchanged-target quality
gate and matched fresh-owner performance checks.
