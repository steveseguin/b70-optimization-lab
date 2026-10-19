# What packet141 can and cannot split

The input is the completed packet141c diagnostic on bundle8: rank0's 24-layer
half at position133. This is **not a measured B half or a one-card layer sum**.
Applying its costs to B's 24 layers or all 48 one-card layers is an explicitly
unmeasured proxy. The original packet141 analyzer refused the declared versus
actual touch-plan kernel counts. Packet164 preserves that refusal: 31 sites
declare one event but execute two; the actual complete half contains 561
events. Route and router each agree at 24 events. This new diagnostic parser
checks complete event order against the retained actual plan, all four cold
halves, all 16 retained warm virtual halves, all four natural halves, and all 16
whole-state/route equality receipts. It does not repair or qualify packet141.

Aggregate by summing durations within each complete half, then taking medians.
Warm rows use repeat indices 2–5, excluding 0–1. Warm gaps include diagnostic
restores and are deliberately not treated as launch time. Cold and natural
gaps are measured between successive event end/start clocks.

| Quantity per 24-layer half | Cold a | Warm b | Natural |
| --- | ---: | ---: | ---: |
| Route kernel sum, ms | 0.792448 | 0.750990 | 0.792865 |
| Route kernel calls | 24 | 24 | 24 |
| Router kernel sum, ms | 0.535729 | 0.288596 | 0.535989 |
| Router kernel calls | 24 | 24 | 24 |
| Router-end to route-start gaps, ms | 0.003073 | not attributable | 0.003021 |
| Route-end to expert-gate-start gaps, ms | 0.002970 | not attributable | 0.003020 |
| All between-event gaps, ms | 0.081189 | not attributable | 0.081715 |

The two route-adjacent gaps are **outside** the 0.792448 ms kernel sum, not a
partition of it. They are not pure launch overhead or a causal dependency
measurement. Host submission may overlap prior work; GPU event duration can
include internal memory/barrier stalls. There are no host enqueue timestamps
or internal phase clocks here. Even all observed issue gaps in the entire
half are below 0.4 ms, but that does **not** bound internal kernel latency.

| Requested split | Existing evidence |
| --- | --- |
| Launches | 24 route calls, one per layer; no separate top-k/normalization/publication launches |
| Dependent waits | 24 router→route and 24 route→expert boundaries; aggregate visible gaps above; internal waits unmeasured |
| Top-k | Inside each route call: p78/p109's 45-round 512-value bitonic network, lower-ID tie rule; phase duration unavailable |
| Normalization | Original 512 exponentials;32 adjacent 16-leaf sums, unchanged denominator tree and rounded division; selected 10 tree and second division; phase duration unavailable |
| Publication | IDs, FP32 probabilities, two 10×3 expert descriptors, plus p109's 640-element shared activation; phase durations unavailable |

**Latency fraction is unidentified, not zero.** Its evidentiary range within
the route event is 0–0.792448 ms/half; a 0.4 ms removable component is unproved.
Small input size and static instruction/barrier counts cannot supply that
missing measurement (packet33). Packet112 reduced barriers 27→14 but saved
only 1.250/1.354 µs in its two fresh micros; do not transfer those isolated
micro durations into this cold fused route. Route's cold/warm ratio is 1.0552;
router's is 1.8563. Neither ratio tells us what fusion can remove.

The router class already owns the independent router/shared-gate/shared-up/
scalar-gate tuple, not just one router GEMV. All four projections remain
required. See p141 `p39_plan.hpp`, `p49d_small.hpp`, `engine_fusion.hpp` and
`p109_route.hpp`; [design](DESIGN.md) keeps their arithmetic boundaries.

## Individual route calls

Cold medians below are descriptive per-site values in microseconds. **Do not
sum these medians** to reproduce the half total. All 24 sites appear in every
sample; raw ranges and warm/natural per-kernel rows are in
[analysis.json](evidence/analysis.json).

| Layer | µs | Layer | µs | Layer | µs |
| --- | ---: | --- | ---: | --- | ---: |
| 0 | 33.5415 | 8 | 33.1250 | 16 | 33.0205 |
| 1 | 33.1770 | 9 | 33.2290 | 17 | 33.2290 |
| 2 | 33.3340 | 10 | 32.9165 | 18 | 32.8650 |
| 3 | 32.8120 | 11 | 32.7085 | 19 | 32.9170 |
| 4 | 32.8645 | 12 | 33.0210 | 20 | 33.0730 |
| 5 | 33.2290 | 13 | 32.8645 | 21 | 32.9170 |
| 6 | 33.3335 | 14 | 33.1250 | 22 | 32.9685 |
| 7 | 33.0205 | 15 | 32.7080 | 23 | 32.7085 |

## Priced ceilings, not predictions

One-card pricing reaggregates all 12 packet58aj WS128 prompt rates by class;
baseline 31.966819788 tok/s. Two-card pricing exactly reconstructs packet160's
1,188 packet136 intervals and 58.798108759 tok/s. It uses:

`max(D, R+C) + max(B, A+offset) + unresolved_gaps`.

Cut B and optionally corrected C; also show a whole-target implementation
that cuts A as well. Never count equal A and B savings twice. For large B-only
cuts, A becomes the limiting half. C savings occur only on misses and can be
hidden behind D. This is why a simple subtraction from 14.70 ms is insufficient.

| Counterfactual | Transfer | Saving/half ms | One-card48-layer proxy ms | One-card gain | B-only gain | B+C gain | A+B+C gain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Delete all route work | 100% | 0.792448 | 1.584896 | 5.343% | 3.819% | 4.894% | 5.985% |
| Delete all route work | 20% | 0.158490 | 0.316979 | 1.025% | 0.941% | 1.142% | 1.142% |
| Delete route AND entire fused router | 100% | 1.328177 | 2.656354 | 9.291% | 3.852% | 5.667% | 10.454% |
| Delete route AND entire fused router | 20% | 0.265635 | 0.531271 | 1.729% | 1.587% | 1.929% | 1.929% |
| Hypothetical 0.4 ms latency removal | 100% | 0.400000 | 0.800000 | 2.627% | 2.409% | 2.934% | 2.934% |
| Hypothetical 0.4 ms latency removal | 20% | 0.080000 | 0.160000 | 0.515% | 0.473% | 0.573% | 0.573% |

The +2% one-card threshold is **0.612738 ms/token net**, or 0.306369 ms per
24-layer proxy. That requires recovering 38.661% of the entire route class,
or 23.067% of route plus router. Those percentages already assume no added
atomic, occupancy, synchronization, activation or capture costs. The 20% factor
is the requested conservative transfer scenario from earlier work, **not a
measured law or hard physical ceiling**. CPU parity does not change it.

Decision: the specific latency-fusion build gate remains unpassed. Retain the
[conditional brief](briefs/onecard.md), because the mathematical raw ceiling
does exceed 2%; require new mechanism/latency evidence before treating it as a
selected build. No READY, executable proposal, GPU build or speed claim.
