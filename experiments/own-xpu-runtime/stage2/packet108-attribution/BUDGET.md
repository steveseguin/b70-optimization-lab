# Packet 108: what the current receipts can attribute

October 18, 2026. Existing evidence only; no device launch. The current
packet97 + down-tile16 line takes about **15.18 ms on a hit and 26.09 ms on a
miss** on lane A. Rank1's target half remains slower than rank0's speculation
by about **0.52–0.54 ms on hits**. Drafting costs about **1.78 ms** and precedes
both target halves on a hit. These are fresh measured host command times.

**A fresh per-class GPU budget is unavailable.** The current performance runs
retain command traces and host timers, but their `rank*/sites.jsonl` files are
empty. Packet100/104 micros provide operator ratios, not full-model class
costs. Historical sampled class costs are separated below; none is passed off
as a current class measurement, divided into invented hit/miss costs, or
silently scaled by a microbenchmark ratio.

[budget.json](budget.json) records twelve runs, every numerical field below,
site-file availability, operator qualification ratios, and SHA256/size pins
for 559 evidence/code inputs. [extract.py](extract.py) reproduces it using only
the standard library and the hash-bound existing packet85 command-join helper.
No raw logs are copied. From the repository root:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet108-attribution/extract.py --output /tmp/p108-attribution-check.json </dev/null
cmp experiments/own-xpu-runtime/stage2/packet108-attribution/budget.json /tmp/p108-attribution-check.json
```

## Timing definitions and dependency budget

Each 128-token request contributes its first **99 emission intervals**. The
twelve-request runs give 1,188 intervals: **936 hits and 252 misses**. The
single packet105 smoke contributes 63 intervals: 53 hits and 10 misses. A
hit/miss labels the guess verified at the **starting emission**; one interval
produces one verified token. These tables pool conditional interval means;
they are not the throughput headline's median of prompt-class medians, nor the
summary's full-127-interval median of per-prompt hit/miss means.

Use the shared host monotonic clock. Do not compare GPU timestamps between
cards. The previous speculative half is already complete at the starting
emission; adding it would count work twice. `A` below is the **next** rank0
speculation. The measured dependency graph is:

```text
hit  = D + max(B_hit, A + start_offset) + control_gap
miss = max(D, R + C) + max(B_miss, A + start_offset) + control_gap
D = rank1 draft; R = rank0 restore; C = corrected rank0 target half
B = rank1 target half; A = next rank0 speculative target half
```

Primary current evidence is
[`p104b-B-grid-A-0-production/summary.json`](../screen/v4-lanes/evidence/p104b-B-grid-A-0-production/summary.json),
the first lane-A control, measured at 57.257151 tok/s. The later control is
57.240491 tok/s and has nearly identical component costs. The strings `B-grid`
in these filenames describe the driver action; `A` identifies the actual lane.

| Fresh host budget, ms per interval | Rank0 hit | Rank0 miss | Rank1 hit | Rank1 miss |
| --- | ---: | ---: | ---: | ---: |
| Next speculative target half | 12.859200 | 12.855727 | — | — |
| Corrected target half | 0 | 11.878631 | — | — |
| Rollback including restore | 0 | 0.549849 | — | — |
| Target half including head | — | — | 13.376682 | 13.647039 |
| Draft command | 0 | 0 | 1.777447 | 1.772728 |
| Union of all host command envelopes | 12.859465 | 25.284439 | 15.154351 | 15.419989 |
| Outside host command envelopes | 2.314000 | 0.804205 | 0.019113 | 10.668655 |
| Full interval, common clock | 15.173465 | 26.088644 | 15.173465 | 26.088644 |

The envelope union clips each command to the emission interval, merges
overlaps, and includes short accept commands. Therefore its sum need not
equal the independently displayed component means exactly. Outside-command
time is **dependency wait/control time, not measured GPU idle**. In particular,
rank1 waits for rank0's corrected work on misses; speeding up the draft there
does not shorten the cycle. Rank0's 2.314 ms outside commands on hits contains
draft wait plus approximately 0.518 ms target-race slack; it is not all usable
slack for an independent parallel kernel.

Remaining DAG control gaps are **0.019336 ms hit / 0.013125 ms miss**. The
ready-branch-to-rank1-start boundary is 0.011711/0.004354 ms, draft issue after
emission is 0.006634/0.006643 ms, and final race-to-emission is
0.000991/0.000999 ms. These boundaries are already inside the residual; do not
add them again or call them pure transfer latency.

## Every requested GPU class: current observability

| Class | Rank0 hit/speculation | Rank0 miss/correction and speculation | Rank1 hit | Rank1 miss |
| --- | --- | --- | --- | --- |
| MoE gate/up | Not separately timed | Not separately timed | Not separately timed | Not separately timed |
| MoE down | Not separately timed | Not separately timed | Not separately timed | Not separately timed |
| Shared expert | Not separately timed | Not separately timed | Not separately timed | Not separately timed |
| HC | Not separately timed | Not separately timed | Not separately timed | Not separately timed |
| QSA | Not separately timed | Not separately timed | Not separately timed | Not separately timed |
| GDN | Not separately timed | Not separately timed | Not separately timed | Not separately timed |
| Dense attention projections | Not separately timed | Not separately timed | Not separately timed | Not separately timed |
| Target head | Not owned on this baseline rank | Not owned on this baseline rank | Included in target envelope | Included in target envelope |
| Draft GPU work | Not owned on this baseline rank | Not owned on this baseline rank | GPU sum unknown; host envelope above | GPU sum unknown; host envelope above |
| Transfers | Included in command envelopes | Included in command envelopes | Included in command envelopes | Included in command envelopes |
| Launch gaps / actual GPU idle | Not observed | Not observed | Not observed | Not observed |

The fresh host timers still reveal work worth investigating. Means below
come from the first control's 1,188 speculative rank0 halves, 252 corrected
rank0 halves, and 1,188 rank1 target halves in the selected position window.
The speculative sample is keyed by its own position, while the dependency
table uses the next position; this timer table is not a pointwise DAG sum.

| Timer | Rank0 speculative | Rank0 corrected | Rank1 target |
| --- | ---: | ---: | ---: |
| Launches issued | 636 | 636 | 628 |
| Enqueue loop, ms | 2.753591 | 2.742816 | 2.746605 |
| Prepare, ms | 0.104810 | 0.104678 | 0.000025 |
| Retirement, ms | 0.114516 | 0.109734 | 0.043341 |
| Profiling queries, ms | 0.000075 | 0.000043 | 0.426989 |
| Wait timer, ms | 9.193339 | 8.797837 | 10.062845 |

Enqueue overlaps device execution, and waiting includes device completion;
neither is an independently removable cost. The 0.427 ms profiling-query
timer is real host work, also present as 0.429 ms in packet97's chain. Its
exposed fraction is not measured. `packet103-record-bundle/main.cpp::drain`
queries pending events and checks the declared four-second per-submission
budget; deleting that safety check is not a qualified optimization. New
query batching would need its own proof. The 3.4–5 µs launch-cost premise also
cannot be multiplied by all launches and added to the target envelope:
submission and GPU execution overlap.

## Comparisons retained separately by identity

All rates below are the stored class-balanced first-99 metric. H/M are newly
extracted pooled first-99 means. These screens are not new record chains.
The packet100/101 controls used earlier packet97 selection choices; they must
not be substituted for the later packet104b composed baseline.

| Source run | tok/s | H ms | M ms |
| --- | ---: | ---: | ---: |
| p97 chain-b WS128 | 56.086987 | 15.498869 | 26.592599 |
| p100 lane A control0 | 55.481372 | 15.669530 | 26.845707 |
| p100 lane A down-tile16 | 56.642811 | 15.349053 | 26.344292 |
| p100 lane A control2 | 55.473073 | 15.677496 | 26.871003 |
| p101 lane A control0 | 55.579422 | 15.639732 | 26.776871 |
| p101 lane A draft_attention | 55.755813 | 15.552198 | 26.820126 |
| p101 lane A control2 | 55.601093 | 15.625282 | 26.782917 |
| p104b lane A control0 | 57.257151 | 15.173465 | 26.088644 |
| p104b lane A control2 | 57.240491 | 15.188609 | 26.090978 |
| p104b lane B control0 | 57.109803 | 15.202819 | 26.194260 |
| p104b lane B control3 | 57.124659 | 15.196276 | 26.173925 |
| p105 smoke, candidate only | Not comparable | 15.344350 | 27.315434 |

Packet100's real-route down micro gives about **0.695×** production kernel
time, while its matched lane-A screen improves 2.09%. Packet104 target
gate/up transposition gives about 0.898× (0.893× with half-cache), but its model
screens show no gain. These observations rule out treating micro gains as
whole-model gains. Exact ratios for every micro arm and the original
qualification-source hashes are in `operator_micros` in the JSON.

The p105 smoke is one 64-token prompt. It passed that narrow check, but the
same packet105 lineage later **failed architecture-tradeoff's every-token
oracle**. It is not a current valid baseline or a gain measurement; packet105b
reset repairs require their own complete evidence. The smoke's 64 host
transfer envelopes per leg have mean/median microseconds: rank0 hidden import
28.177/22.372, rank0 best export 22.883/22.337, rank1 prefix export
26.072/25.844, rank1 hidden export **8833.705/8935.110**. The last includes
waiting for the hidden-state producer, so it emphatically is not an 8.8 ms
DMA. All four are already inside their host commands. Sources and failure
note are hash-bound in the JSON.

## Historical class budget and byte references, not current measurements

The newest complete retained broad per-class table is
[packet77's attribution report](../screen/v4-lanes/evidence/packet77-attribution-B-a/run/attribution-summary.md).
It samples layers22/23 on rank0 and24/27 on rank1, then multiplies call medians
by 18 GDN and6 QSA occurrences per half. Rank0 uses completed corrected work,
which is miss-conditioned. It does not independently measure speculative or
hit-conditioned class times. The selection is packet70 draft-HC, wide64,
batched rollback, placement1, before several later exact improvements.

Numbers below are **sample-scaled estimates**. The byte reference divides
source-derived useful reads by **555 GB/s**, the existing packet77 calibration
reference. It excludes a full transaction/write/compute model. Cache hits,
instruction dependencies, reductions, dequantization and launch overhead
prevent interpreting the difference as achievable speedup. No numerical
compute floor is justified by the retained instruction/occupancy evidence.

| Historical category | R0 ms/half | R1 ms/half | Useful-read reference ms/half |
| --- | ---: | ---: | ---: |
| MoE gate/up | 1.476870 | 1.490925 | 0.454108 |
| MoE down | 1.252497 | 1.263432 | 0.399088 |
| HC, all labeled HC sites | 2.142804 | 2.163765 | 0.660729 |
| GDN, projections and recurrence | 2.883762 | 2.842506 | 1.793253 |
| QSA, projections and attention | 1.056564 | 1.061874 | 0.499500 |
| Dense attention output projections | 1.120929 | 1.155006 | 0.853385 |
| Shared down and activation only | 0.364383 | 0.363762 | 0.079872 |
| Fused router + shared gate/up | 0.531240 | 0.526248 | 0.404508 |
| Other route, mixture, activation, combine | 1.020624 | 1.023453 | 0.005063 |

The shared gate/up cannot be split from the fused router using these events.
The target head was separately measured at **1.403684 ms** in this old
instrumented run, reading794,629,120 useful bytes; /555 GB/s gives1.431764 ms.
Being faster than that reference illustrates why it is not a hard hardware
floor. Final norm/merge was0.051563 ms; argmax0.022874 ms. The old1.544260 ms
unattributed host remainder includes observer work and unsampled activity;
it cannot be labeled GPU idle or copied into the current budget. Old target
copy timestamp fields were zero-width and do not establish zero transfer cost.

Historical draft GPU events sum categories: prefix0.520766 ms,
attention0.387236, HC0.250633, experts0.251424, shared expert0.044405,
embedding0.060166, argmax0.021087, other0.006189, transfers0.002612.
Those buckets are inside the draft command, not additional critical-path
costs. Packet101 later changes draft attention. Packet86's more recent narrow
production diagnostics report gate/up1.495 ms, down1.208 ms and HC
attention/FFN gates0.604/0.592 ms on rank1; they do not supply a complete
fresh class budget for p97 + tile16.

## Top three remaining exact levers

These are planning judgements, not measured gains. Probability means a
subjective chance of clearing the micro, exactness and model-transfer gates;
the product ranks one small experiment, not a forecast of a new record.
Use 57.25 tok/s only as a local sensitivity anchor. No projected number is
eligible for a result packet, public table or submission.

| Priority | Exact change | Conditional gain, tok/s | Probability | Midpoint × probability |
| --- | --- | ---: | ---: | ---: |
| 1 | Draft `mtp36::lane<K,true>` raw eight-value loads; original WG128/SG32 | 0.057–0.113 | 0.50 | 0.043 |
| 2 | IQ4 DOWN subgroup-register level lookup; unchanged tile16 layout | 0.10–0.30 | 0.15 | 0.030 |
| 3 | Interleave shared gate/up workgroups in the fused small-GEMV tuple | 0.02–0.08 | 0.20 | 0.010 |

1. **Draft load grouping, implemented in packet108.** In
   `packet103-record-bundle/mtp_kernels.cpp`, gather eight INT8 codes, the one
   FP32 scale covering those eight values, and eight BF16 inputs at once.
   Retain `scale*code`, then `value*input`, then the original sequential sum,
   followed by the same 32-lane adjacent reduction. Gate/up K=2560 and DOWN
   K=640 keep their full banks and status semantics. Packet59 already has the
   load technique, credited locally; its V8/V16 work assignment, WG256 and
   optional fusions confounded that test. This isolates loads at production
   WG128. It is not packet104's losing transpose or packet81's target IQ2/IQ4
   packed-input experiment. The historical packet69 **operator-only** means
   are 82.387 + 63.685 = 146.072 µs, excluding checks/combine. A hypothetical
   15–30% cut removes 21.91–43.82 µs from hits. With hit fraction 936/1188,
   `57.25² × hit_fraction × saved_seconds` gives the range above. The current
   class cost and achieved saving remain unknown. This is small enough for
   one micro and prompt closure, not an extended geometry campaign.
2. **IQ4 level lookup, deferred.** Replace `p33::level_bank`'s packed byte-bank
   selects and variable shifts in `p100::tile_chains` with a lane-held level
   and `select_from_group`. Keep the signed level values, half conversion,
   scale multiplication, sums, tile16 storage and WG64 unchanged. The current
   decoder already uses registers; the distinct hypothesis is fewer integer
   instructions through subgroup lookup, not merely "put the table in
   registers." Packet99 used an IQ2 SLM byte-pair table and spilled; packet33's
   conditional decoder and packet81's input-load count are also distinct.
   Require a linked assembly check for a real instruction reduction and zero
   new spills before a real-route micro. Shuffle latency may erase all benefit.
   The range is deliberately speculative, allowing about 20% engine transfer;
   it is not computed by scaling an old class time into the current engine.
3. **Shared tuple scheduling, deferred.** `p49dvirtual::SmallKernel` issues
   router groups, then gate groups, then up groups. Map matching gate/up
   workgroups next to each other while retaining each independent Split4
   group, original addresses, output indices and reduction. This changes
   submitted group ordering only, not packet104's weight layout or packet102's
   per-thread sharing. Device dispatch order and cache benefit are unproved;
   that is why it ranks last. Do not repeat a broad occupancy sweep.

Other strong-looking sites already have owners or closed mechanisms:
105b/106b head splits and 107 QSA are in flight; GDN specialisation is closed
by Intel NaN payload inequality. Gate/up packets95/99/102/104 remain closed.
The 0.427 ms host profiling timer deserves separate dependency analysis, but
its exposed cost is unknown and it is not a real-route kernel micro lever.

The following bounds constrain all three:

- Draft cuts move the hit critical path directly until another dependency
  changes; draft cuts do not shorten the measured misses.
- Rank1 target cuts consume only about0.52 ms of hit slack before rank0
  becomes limiting. Rank0 speculation-only improvements have no local gain
  while that slack remains. Rank0 corrected-work cuts help misses.
- At a57.25 tok/s anchor and the pooled hit fraction936/1188, removing0.1 ms
  from the draft on hits is approximately+0.26 tok/s; removing0.1 ms from
  rank1 on both paths is approximately+0.33 tok/s. These are conditional
  sensitivity calculations, not measured gains or promises.
- No repeated gate/up layout campaign follows packet104b's loss. Head-row
  splitting and QSA specialization already have separate in-flight packets.
  The historical useful-byte excess is not permission to reopen a closed arm.

Current evidence therefore supports a small, exact draft-kernel micro first,
with real-route replay and an unchanged arithmetic/quality gate, before any
new full model campaign. A measured micro threshold still does not establish
engine transfer or authorize a record claim.
