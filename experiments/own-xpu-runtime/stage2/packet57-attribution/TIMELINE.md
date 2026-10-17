# Packet 57: what packet 56's actual engine timeline says

CPU analysis only, 2026-10-17. No new device run and no speed claim. Source:
packet56 `device-cards01-a/WS128/run/repeat-1/*/receipt.json`, its common-clock
`rank_trace` and generated-token timestamps. [timeline.json](timeline.json)
binds all 36 input receipts by SHA-256, including packet49d and packet49c.
It records full per-prompt summaries without copying output tokens.

**Rank 0 is now the usual limiting target half. A whole-layer move is too coarse
on the available average-half estimates. The draft is still a useful hit-path
lever, while wrong guesses leave rank 1 waiting for the correction.**

## Reproduce

From the repository root, using only Python's standard library:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage2/packet57-attribution/timeline.py --output experiments/own-xpu-runtime/stage2/packet57-attribution/timeline.json
nice -n 19 taskset -c 4-15,20-31 python3 -B -m unittest discover -s experiments/own-xpu-runtime/stage2/packet57-attribution -p test_timeline.py
```

Use `--receipts-root` to relocate the three retained result directories. The
analysis takes about two seconds here, does not open model weights, and reads
neither warmup output nor another window into the timing comparison. Seven
CPU checks cover interval union/clipping, preceding-guess cycle assignment,
missing/duplicate commands, terminal cycles and hit/miss draft overlap.

## Scope and definitions

Twelve prompts, 128 generated tokens each: **1,524 inter-token intervals after
TTFT**, 1,197 hits and 327 misses. Pooled acceptance is **78.5433%**; median
per-prompt acceptance is **78.7402%**, explaining the brief's rounded 0.787.
The first token has no preceding decode interval. The final interval of each
request has no next speculative half, so all measured-cycle/idle summaries
retain it, but model, bottleneck and split calculations use **1,512 complete
pipeline cycles**. All twelve output hashes match both older packets.

A guess decided at target completion `t_i` determines the work in
`[t_i,t_(i+1)]`. The script joins by position and preceding completion, rather
than labeling an interval with its ending guess. Native `guess_rows.cycle_ms`
includes the correction after the current loop; `draft_rows.cycle_ms` measures
the following emitted-token interval. They are not interchangeable per-cycle.

- **D**: published draft wall time for the next cycle. This includes draft
  computation and publication work; it is not a GPU kernel sum.
- **S**: rank-0 speculative HALF command envelope, including snapshot and
  preparation/retirement work.
- **B**: rank-1 target HALF envelope, including its head and final operations.
- **R**: rank-0 ROLLBACK envelope, including drains and restoration.
- **A**: rank-0 corrected HALF envelope after a miss.

Command envelopes are `rank_completed - rank_received` from one host monotonic
clock. The native controller supports an asynchronous draft; B can enclose
pending draft work, and host publication observation is not a GPU timestamp.
`hit = D + max(S,B)` and `miss = max(D,R+A) + max(S,B)` are therefore approximate
models, checked below against actual cycle timestamps, not exact partitions.

## Measured packet 56 timings

Each table entry below is a median of individual cycles (milliseconds).
Medians of different columns do not add exactly.

| Phase or observation | Hit | Miss |
| --- | ---: | ---: |
| Emitted-token cycle | 18.1209 | 33.1068 |
| D, draft wall | 1.9030 | 1.8890 |
| Enclosing DRAFT command | 1.9269 | 1.9124 |
| S, speculative rank 0 | 16.1467 | 16.7567 |
| B, target rank 1 | 15.9551 | 16.1034 |
| R, rollback | 0 | 1.6111 |
| A, corrected rank 0 | 0 | 14.7547 |
| Actual cycle minus model | +0.0613 | +0.0270 |
| Rank 0 without a host command | 1.9686 | 0.0267 |
| Rank 1 without a host command | 0.3110 | 15.0770 |
| Rank 1 finish slack while rank 0 completes | 0.2796 | 0.6413 |

The median-of-request-means definition from the previous notes is
**18.219585 ms hit / 33.043510 ms miss**, reproducing the brief. Means over all
individual intervals are 18.221289 / 33.048989 ms. These statistics are neither
the class-balanced submission rate nor substitutes for its exact window.

Rank 0 completes last in **1,411/1,512 cycles (93.32%)**. Rank 1 does not get
another 0.9 ms of target work budget when D shrinks: D precedes both halves on
a hit. Shrinking it moves both halves earlier. On a miss the roughly 16.4 ms
rollback-plus-correction path dominates D and exposes about 15 ms of rank-1
host inactivity, while rank 0 has almost no uncovered host time. This is a
structural serial dependency, not 15 ms of removable mailbox overhead.

## Waits and idle: what the receipts do and do not measure

| Observed host interval, median ms | Hit | Miss |
| --- | ---: | ---: |
| Target completion observation to next draft send | 0.01538 | 0.01508 |
| Rank-1 HALF send to worker receive | 0.00694 | 0.01021 |
| Host wait observing draft publication | 0.00862 | 0.00012 |
| DRAFT command completion to rank-1 HALF receive | 0.01486 | 14.47001 |
| Rank-1 HALF receive to speculative rank-0 receive | +0.00323 | -0.00677 |

Negative start skew on misses means rank 0 enters its local half before the
worker receives the already-sent request. The large miss handoff gap is waiting
for corrected rank-0 state, not transfer latency. The receipt's
`rank0_to_rank1_handover_ms` similarly includes dependencies and is not a PCIe
measurement. The half `wait_ms` in per-rank `timings.jsonl` means the host waits
for submitted GPU work; calling it idle GPU time would reverse its meaning.

The idle rows are cycle wall time minus the **union** of clipped command
envelopes. They are measured host no-command intervals, **not measured GPU
idle**: a command can contain device inactivity, and asynchronous device work
can outlive its issuing host command. The split of D's remaining work requires packet 57's device events.
Accurate full-device idle additionally requires a complete device timeline;
packet 57's selective attribution does not supply that. Existing `gpu_ms=0`
fields do not mean that those target kernels took zero time; deferred draft
GPU values may also land in the next HALF's cumulative counter.

The leftover argmax/transfer cannot simply overlap the same guessed-token
rank-0 start: that start needs the argmax result. Publication already uses
ordered asynchronous copies. The tiny observation/mailbox gaps above are the
measured control candidates; none separately measures argmax or transfer.
Even removing **all** D is only a model upper bound of +7.52% (below), so a claim
of saving a whole head again by overlapping its result would be unsupported.

## Compare packet 49c, 49d and 56

| Receipt statistic | 49c | 49d | 56 |
| --- | ---: | ---: | ---: |
| Hit, median of request means, ms | 19.1635 | 19.0223 | 18.2196 |
| Miss, median of request means, ms | 33.2017 | 32.8109 | 33.0435 |
| D median, ms | 2.7772 | 2.7825 | 1.9004 |
| S median, ms | 16.1382 | 16.1578 | 16.1620 |
| B median, ms | 16.3099 | 15.9752 | 15.9949 |
| Rank 0 finishes last, complete cycles | 781/1512 | 1377/1512 | 1411/1512 |
| Hit count, all generated intervals | 1208/1524 | 1208/1524 | 1197/1524 |

The head prefix transfers into D: **0.8821 ms less than 49d**. S and B scarcely
change relative to that saving. 49d's improvement relative to 49c mainly shows
on B; these separate single-owner windows are retrospective attribution, not
a new two-fresh-owner performance verdict. The prefix changed 11 of the net
hit outcomes while all target output hashes stayed equal. Do not attribute
all miss-time movement to the prefix: miss membership and run conditions vary.

## Split sensitivities, not measured per-layer forecasts

**No measured per-layer times exist in these receipts.** KD has two retained
site files; WS, WS128x and WS128 each have 30; all **92 are empty**. They cannot
supply layer 22/23 timings. Actual launch plans identify layer 22 as GDN on
rank 0 and layer 23 as QSA on rank 1, so the candidate moves are not equivalent.

The only pre-run numerical sensitivity available uses measured whole-half
medians divided by layer count: S/23 = **0.70270 ms**, corrected A/23 =
**0.64151 ms**, B/25 = **0.63979 ms**. Those are **average-half proxies**: S
includes snapshot/coordination and B includes the target head. They are not
measurements of the boundary layer or claims that overhead moves with a layer.
The script applies the delta to each paired cycle and retains its model
residual; no throughput point is promoted from this arithmetic.

| Hypothetical split | Recovery contribution, ms/cycle | Parallel-halves contribution, ms/cycle | Total change | Relative rate sensitivity |
| --- | ---: | ---: | ---: | ---: |
| 22/26, one layer from rank 0 to 1 | -0.13704 | +0.24997 | +0.11293 ms | **-0.53%** |
| 24/24, one layer from rank 1 to 0 | +0.13704 | +0.69586 | +0.83290 ms | **-3.75%** |

The starting mean is 21.391283 ms across the 1,512 complete cycles, not the
record's class-balanced rate. For 22/26, shorter correction helps only misses;
increased B then costs every cycle once it exceeds S. Under the same rank-0
removal proxies, the destination layer must cost **less than 0.52526 ms** to
break even, versus the crude B/25 proxy of 0.63979 ms. Instrument layer 22 and
23 in engine before proposing a split run. The current evidence does not rank
split movement ahead of draft or rank-0 work.

Moving the draft to rank 0 with the present protocol is also unattractive:
on misses it shares rank 0 with rollback/correction, replacing `max(D,R+A)`
with serial `D+R+A`. Holding D constant and charging **zero** new reverse-hidden
transfer cost gives **+0.40470 ms/cycle, -1.86% rate**. Actual placement could
change memory fit and D, neither of which these receipts measure. On hits,
same-D placement has no inherent formula benefit.

## Pre-run value bounds for the lever ranking

Holding target halves, acceptance and correction unchanged, draft saving only
shortens hits. Per-cycle delta arithmetic gives:

| Hypothetical D reduction | Mean cycle saved | Relative rate sensitivity |
| --- | ---: | ---: |
| 0.5 ms | 0.39319 ms | +1.87% |
| 1.0 ms | 0.78638 ms | +3.82% |
| Remove all D, impossible ideal bound | 1.49697 ms | +7.52% |

These are conditional model sensitivities, not predicted benchmark records.
The remaining approximately 1.34 ms inferred from old isolated head timing
has never been assigned to draft kernels in the engine. Packet 57 must measure
that attribution and its perturbation before choosing attention, INT8 experts,
shared expert, norms or transfers. Rank-0 speculative/snapshot and corrected
work remain larger structural opportunities; packet 57's selected target-layer
profile will show which portion is actually worth changing.
