# Packet58ao — next one-card compute lever

October 19, 2026. **Close at the ranking gate; do not build packet58ap.**
No remaining exact lever has evidence supporting at least +2% on packet58aj.
This is the requested conditional no-build outcome, not a claim that the
one-card lane is finished. Packet58am owns the demand-transfer experiment.

The current record is **31.9668197878 tok/s**, one B70, target-only decode,
quantized compressed Unsloth UD-IQ3_XXS, unchanged `iq3-p49-split32-v1`, full
BF16 KV, context4096, 21,552,729,600-byte expert cache, resident lookup copies.
The twelve cold prompts use 128 output tokens and the first 99 inter-token
intervals after TTFT. Strict512 remains false. This audit creates no new
performance, quality, device-readiness or publication claim.

## Decision and remaining exact lever

**Top applicable unported accepted mechanism: p82/82b `rec-both-plus`.**
It separates Q/K preparation and gate producers, and removes the initial
guard-only workgroup barrier while preserving FP32 operation order, reduction
trees, BF16 state writes and sticky-error behavior. Its ordinary target shapes
are 48 heads, 128-wide state rows, 786,432 state elements, 1,536 four-row
workgroups, 36 GDN layers over the full one-card model. No draft is needed.
The one-card compiled port exists in 58j, but 58aj still uses rows4-shared;
the [inventory](INVENTORY.md) distinguishes source presence from selection.

It **does not pass this brief's build gate**. The earlier exact one-card
route+recurrence screen produced only **+0.37% strict**, less than its 0.5%
gate and smaller than 1.18% control drift. It was explicitly closed
[in the result note](../../../../notes/2026-10-18-own-runtime-packet58r-result.md).
Route-fast is now already present inside p109, so that historical combined
effect cannot even be assigned entirely to the remaining recurrence change.
The two-card source bracket's +0.6381% route+recurrence gain is historical,
not a matched one-card bound. No new isolated evidence overturns the closure.

The strongest broader compute hypothesis found in p140/p147 is **same-bit
scale multicast across all eligible dense sites**. This is a previously
ranked, unimplemented design, not a newly accepted mechanism. Even doubling
the old half-model proxy and retaining its provisional 20% transfer gives
only **0.365141 ms/token, +1.1823%** on the real 58aj prompt means. It needs
**33.56% transfer** of already assumed raw savings to reach +2%; 80% would give
+4.9032%, but there is no evidence supporting that assumption. Earlier
load-count reductions transferred near zero. Neither an arbitrary transfer
factor nor deleting the complete compute tail is a supported ceiling for an
implementable lever. The sensitivity numbers are not measurements or forecasts.

## What the current timings actually support

[analyze.py](analyze.py) replays all twelve requests from both final WS128
windows, verifies stream hashes against each window, checks exactness/identity,
recomputes each 99-interval rate and then all six class medians. The first
prompt is retained. Each window supplies **1,188** charged timing rows. The
results reproduce both saved records to less than 1e-8 tok/s. Prompt and output
hashes match between the two windows. These are old recorded exactness results,
not a fresh model/oracle execution.

| Measured field, arithmetic mean over charged token rows | 58ah chain b | 58aj chain a |
| --- | ---: | ---: |
| Class-balanced rate, tok/s (different aggregation from rows below) | 31.662719 | 31.966820 |
| Token wall, ms | 31.550161 | 31.240099 |
| Host prepare, ms | 0.606399 | 0.206020 |
| Host enqueue loop, ms | 4.962892 | 5.053453 |
| Host wait, ms | 21.470583 | 21.448545 |
| Selected transfer helper spans, ms | 1.712067 | 1.763930 |
| Kernel submissions / host waits | 1,118 / 6 | 1,118 / 6 |
| Process major faults per charged row | 0.019360 | 0 |

The host spans **overlap**. The wait includes compute/transfers/maintenance;
it is not the same definition as 58y's specially split compute-tail wait.
Do not sum these columns into a cost partition. No percentage difference
between the two windows identifies an isolated kernel change.

For 58aj, the reciprocal aggregate is **31.282436 ms**, while mean native
token wall is **31.240099 ms**. Subtracting a uniform saving from each prompt's
mean interval and recomputing the class statistic requires **0.612738 ms/token**
for exactly +2%. This is a screening threshold, not measured removable work.

[58y's report](../packet58y-onecard-attribution/analysis/report.md) records
**20.765729 ms/token** compute-tail wait at **22.8605 tok/s**, with an 18 GB
cache and older kernels. It explicitly says device-class durations and isolated
miss stall are unavailable. The latest 58ah/58aj streams still have zero
placeholder device times and null enqueue-family breakdowns. Therefore a
measured per-kernel ranking **on 58aj cannot be recovered from these receipts**.
Zero-copy misses may reorder any ranking inferred from fully resident kernels.

## Ranked compute classes — diagnostic priority only

This is the available numerical ordering from p140's post-fusion p128b
**two-card rank1 half-model diagnostic**. Its instrumentation overhead gate
failed. These are **not one-card per-token times**, and are not rescaled to
partition the 20.77 ms bucket. All one-card class times remain JSON null.
The table provides a transparent inspection order instead of invented timing.

| Proxy rank | Kernel class | Diagnostic ms/half | Current-line status / exclusion |
| ---: | --- | ---: | --- |
| 1 | Dense attention output, GDN QKV/Z, QSA Q-gate | 3.487164 | Original split32/split4 and BF16 boundaries; p140 scale-multicast hypothesis below gate. Packed loads/layout/tile repeats excluded. |
| 2 | IQ2 gate/up | 1.442975 | Wide64 and exact half-scale decode already adopted. Metadata-cell hypothesis lacks demonstrated transfer; p81/95/99/102/104/115 repeats excluded. |
| 3 | HC gate and mix | 1.060592 | p60 fusion and HC-wide already adopted. p94 duplicated reduction and p117 sigmoid change closed. |
| 4 | IQ4 down | 0.939947 | Tile16 already adopted for cache hits and host misses. Bytepair/warm/geometry retries closed. Miss transfer belongs to 58am. |
| 5 | Remaining small sites | 0.700492 | Expert act/combine, conv, gated norm, QSA prep/pool, other; no separate second credit for p109 fusion. |
| 6 | HC low and inject | 0.566332 | p60 already adopted; preserve low/inject rounding and trees. |
| 7 | Route plus shared activation | 0.542529 | p109 fast route/fusion already present. Rounded probabilities, tie order, invalid-input refusal retained. |
| 8 | Router/shared gate/up tuple | 0.527066 | Independent rows/scales already combined; no duplicate router to evade dependencies. |
| 9 | GDN recurrence | 0.449462 | Only accepted target mechanism still unselected; 58r inconclusive and closed. Proxy uses faster two-card recurrence, not current one-card recurrence. |
| 10 | HC norms | 0.381008 | Producer RMS leaf-partial idea below gate; BF16 stream/version and original tree required. |
| 11 | QSA attention/select | 0.358128 | Existing exact scoring/select; p116 geometry/tree changes closed. |
| 12 | Shared down/mixture/blend | 0.352647 | p109 already adopted; original ordered expert sums/BF16 rounds preserved. |
| 13 | Small GDN a/b and QSA K/V/IQ/IK projections | 0.314042 | No credit for hypothetical scale sharing on F32 paths. |
| Unranked | Full target head, final HC/norm and argmax | Not in this body proxy | Required every token; two-card split head is not portable. Older head timings are not current one-card evidence. |
| Unranked overlay | Zero-copy expert misses | Unknown isolated time | Contained in expert kernels, not an additive row; 58am owns the next causal test. |

The body rows sum to 11.122384 ms/half in that diagnostic only. The table
does not claim a matched 48-layer sum, identical recurrence, current cache
behavior, a measured head cost or a one-card device floor. Details and prior
kernel exclusions are in [p140](../packet140-body-lever/ANALYSIS.md).

| Exact-design sensitivity, using doubled historical raw assumptions | Uniform saving at 20% transfer | 58aj gain at 20% / 80% |
| --- | ---: | ---: |
| Dense-attention same-scale multicast only | 0.139487 ms | +0.4484% / +1.8179% |
| Same-scale multicast across all eligible classes | 0.365141 ms | +1.1823% / +4.9032% |
| IQ2 five-byte metadata cells | 0.115438 ms | +0.3708% / +1.4998% |
| Producer-emitted exact BF16 RMS leaf partials | 0.076202 ms | +0.2444% / +0.9850% |

Even the eligible-site set and raw cuts are optimistic hypotheses. The
20% factor is the earlier audit's cautious screening assumption, not measured
transfer or a positive lower bound; 80% is sensitivity only. Rows overlap and
must not be added. Nothing new establishes a ≥2% build candidate.

## Negative-history audit and exclusions

The audit read and hashed **63 DO-NOT-REPEAT files**, including inherited
copies under every packet58 tree and packet140. The literal `rg` results are
retained in [negative-search.txt](negative-search.txt), with the complete path
list and hashes in [analysis.json](analysis.json). Packet147 has no separate
DO-NOT-REPEAT file; its [PLAN](../packet147-lever-synthesis/PLAN.md) was read
and hashed as its decision record. Historical preparation wording can say
pending even when a later result closed the arm; the dated result governs.

- [58r result](../../../../notes/2026-10-18-own-runtime-packet58r-result.md)
  and [58ag boundaries](../packet58ag-onecard-ports/DO-NOT-REPEAT.md): no
  standalone retry of the route/recurrence arm without new causal evidence.
- [58n](../packet58n-onecard-loo/DO-NOT-REPEAT.md) and
  [58q](../packet58q-onecard-variance/DO-NOT-REPEAT.md): no invented device
  times from disabled counters, host-fault subtraction or cache-hit attribution.
- [58y](../packet58y-onecard-attribution/DO-NOT-REPEAT.md) and
  [58af](../packet58af-onecard-measure/DO-NOT-REPEAT.md): mixed queue waits
  do not isolate miss stalls; no revival of distorted per-site tracing.
- [58ac](../packet58ac-cache-publication/DO-NOT-REPEAT.md): changed-entry
  publication has no demonstrated complete-boundary recovery; the previous
  144-to-one upload optimization is already banked. It is outside compute-tail
  scope and not a fallback qualifying lever.
- [58al](../packet58al-demand-transfer-prep/DO-NOT-REPEAT.md): old p125
  pipeline lost to tile16; actual sparse misses and BCS overlap still need
  the separate 58am test, not a duplicate packet here.
- [140](../packet140-body-lever/DO-NOT-REPEAT.md): no favorable 80% transfer
  assumption, useful-byte roofline subtraction, or readiness from failed
  selection. The current brief lowers the old 3% threshold to 2%; the replay
  applies that new threshold and still does not qualify a candidate.
- [147](../packet147-lever-synthesis/PLAN.md): its missing-HC recommendation
  is now implemented; its small-fusion/E1/HC-wide suggestions are also present.
  MTP/draft/snapshot proposals are outside this target-only task.

## Reproduction and completion

Run from the repository root; these commands read saved small receipts and
source text only, impose a 4 GiB address-space cap and create no runtime:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58ao-onecard-next/analyze.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover -s experiments/own-xpu-runtime/stage2/packet58ao-onecard-next -p test_analyze.py -v </dev/null
```

The analyzer writes stdout only. [analysis.json](analysis.json) retains the
replay, per-prompt metric endpoints/hashes, unknown class times, assumptions,
decisions and input hashes. [Verification](verification.json) records the
replay, failure controls, resource use and input recheck. Some original 58y
analysis bytes were already dirty; they are hashed as observed working-tree
evidence and were not rewritten or treated as a clean upstream revision.

No packet58ap tree, proposals, compile, device execution or READY marker is
created. Consequently the conditional binary-help, preparation/import,
lanequeue/report and native exact-proof gates are not applicable, not claimed
passed. Packet58an is absent from this checkout; no imitation of an unavailable
harness is presented as validated. A future qualifying implementation must
use the complete requested packet58aj closure, real fresh proposal rows,
300-second waits, 25 GB device-window disk floor, 27 GB CPU disk stop, real
entry probes, exactness-only in-run checks and READY last.

All existing packet trees, screen trees, ops files, services and settings were
left untouched. No model/GGUF/full-shape reads, GPU, sudo or live queue change.
See [closeout](CLOSEOUT.md) and [work note](../../../../notes/2026-10-19-own-runtime-packet58ao.md).
