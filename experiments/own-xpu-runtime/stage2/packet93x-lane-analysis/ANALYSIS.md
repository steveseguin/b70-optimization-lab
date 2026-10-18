**Packet 93x — lane-A regression in the packed, transposed head screen**

**Recommendation: pin `head=production` in packet 97's lane-A record
composition.** Head-transpose loses **2.369%** against the mean of A's two
controls, while gaining **0.857%** on B. The A loss is in rank 1's draft and
hit-path target-half commands. It is not a larger inter-command handoff or a
rank-0 bottleneck. Most of the extra draft time is outside its measured GPU
compute events. The receipts establish a run-level regression, but do not
establish a repeatable card defect or layout-placement penalty. Do not dismiss
the loss as noise; do not diagnose card 1 from this one candidate lifetime.

This is a CPU-only retrospective analysis of six existing diagnostic screens.
It changes no selection, queue, runtime, result claim, or frozen packet.
[Machine-readable results](analysis.json) include both windows, per-prompt
statistics, matched differences, source hashes and the decision.
[The reproducer](analyze.py) reads original receipts and packet 85's existing
[position-based command join](../packet85-critical-path/model.py).

**Observed screens and definitions.** Each screen has the same 12 prompts in
six classes, 128 output tokens per prompt, zero cached tokens, and exactly the
same prompt hashes, output hashes, draft guesses and hit/miss sequences.
The primary rate is the median of class medians over the first 99 intervals.
The following hit/miss figures reproduce the brief: they are the median of
12 **per-prompt mean** cycle times over all 127 intervals, rather than the
median of individual intervals. All six summary values were independently
recomputed from the original token-completion timestamps.

| Screen | View | tok/s | Reported hit ms | Reported miss ms |
| --- | --- | ---: | ---: | ---: |
| A-0 | production | 54.959 | 15.777 | 27.045 |
| A-1 | head-transpose | 53.906 | 16.347 | 26.885 |
| A-2 | production | 55.469 | 15.729 | 26.895 |
| B-0 | production | 55.396 | 15.678 | 27.009 |
| B-1 | head-transpose | 55.928 | 15.542 | 26.757 |
| B-2 | production | 55.510 | 15.634 | 26.979 |

The detailed tables below use **pooled interval medians in the first-99
window**, with 936 hits and 252 misses per screen. They therefore need not
equal the reported hit/miss figures above. Per-prompt medians and means, and
the all-127-window summaries, remain in JSON. No additional model run occurred.

`D` is rank 1's draft command. `Bh`/`Bm` are rank 1's target half, including
the target head, conditioned on hit/miss. `A` is rank 0's *next* speculative
half. `R` is rollback and `C` the corrected rank-0 half on a miss. These are
complete command envelopes (`rank_completed - rank_received`), including
host/transfer/wait work. They are not isolated GPU kernel durations.

| Screen | D, hit | Bh | A, hit | Hit interval |
| --- | ---: | ---: | ---: | ---: |
| A-0 | 1.822216 | 13.903459 | 13.373436 | 15.770955 |
| A-1 | 2.123667 | 14.110376 | 13.429767 | 16.258100 |
| A-2 | 1.821809 | 13.804308 | 13.277798 | 15.677359 |
| B-0 | 1.798602 | 13.829719 | 13.320414 | 15.647983 |
| B-1 | 1.794410 | 13.716221 | 13.312563 | 15.524272 |
| B-2 | 1.794713 | 13.816734 | 13.335369 | 15.628901 |

| Screen | D, miss | Bm | A, miss | R | C | Miss interval |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A-0 | 1.805509 | 14.063067 | 13.342223 | 0.587340 | 12.335967 | 27.042197 |
| A-1 | 2.046507 | 13.890724 | 13.404891 | 0.585997 | 12.345660 | 26.877198 |
| A-2 | 1.806376 | 14.018576 | 13.277818 | 0.550154 | 12.288925 | 26.887981 |
| B-0 | 1.789340 | 14.069268 | 13.315108 | 0.555388 | 12.327369 | 26.981225 |
| B-1 | 1.787447 | 13.863808 | 13.307674 | 0.552934 | 12.322478 | 26.737633 |
| B-2 | 1.786257 | 14.056889 | 13.325693 | 0.555993 | 12.334075 | 26.962782 |

All timing-table values are milliseconds. Medians of components do not add
to a median cycle. The dependency model, applied to individual intervals, is:

```text
hit:  D          + max(Bh, A + start_offset) + residual gaps
miss: max(D,R+C) + max(Bm, A + start_offset) + residual gaps
```

The position join matters: the hit flag is the guess resolved at the
*starting* emission; the next interval then pays correction when that guess
missed. Sorting the overlapping trace by serialization order, or associating
the ending emission's hit flag with the interval, gives the wrong attribution.
The JSON records the exact op/rank/position keys. Native draft-row positions
are one less than the draft command position; receipt draft rows are one more.
The reproducer verifies those joins with confirmed tokens, start timestamps
and matching draft wall times.

**The A-1 loss has two components.** Match each prompt and interval position
to the same position in both controls, then average the paired differences.
Using means gives an additive accounting of the observed hit change:

| First-99 mean change, candidate minus mean controls | Lane A | Lane B |
| --- | ---: | ---: |
| Hit interval | +0.563225 | −0.132287 |
| D on hits | +0.374323 | +0.002269 |
| Bh | +0.188370 | −0.133739 |
| Exposed rank-0 tail | −0.000005 | 0.000000 |
| Residual control gaps | +0.000538 | −0.000817 |
| Miss interval | −0.100275 | −0.243989 |
| Bm | −0.141859 | −0.221881 |
| R+C on misses | +0.040745 | −0.021571 |

Thus roughly two thirds of A's extra mean hit time is D and one third Bh.
Rank 0's speculative half grows by 0.083264 ms in mean, but remains hidden
behind Bh. The draft penalty is also present on misses (+0.341395 ms mean);
it is hidden behind about 13 ms of rollback plus correction. Bm still gets
faster, so the miss cycle improves. This resolves the apparent contradiction
between slower hits and faster misses without assuming acceptance changed.

The effect is broader than one unusually slow token: D's per-prompt hit
median rises against the control average in **11 of 12 prompts** on A,
versus 5 of 12 on B. The candidate's hit D medians range from 1.882 to
2.570 ms across A prompts. A's controls also have occasional slower draft
periods (for example A-0's first prompt and A-2's last prompt), so time-varying
host/queue conditions are credible. Tokens within a single process are not
independent fresh-process replications.

**Most extra draft time is not longer GPU arithmetic.** Under `timing=token`,
target events are not profiled, but draft events are. Async draft completion
defers their timestamp queries; the following rank-1 target half drains them.
Its `rank_trace.gpu_ms` is therefore the previous draft's **compute-event
sum**, not the target half's GPU time. This follows from
[main.cpp](../packet93-packed-head2/main.cpp) lines 660, 678–694 and 705,
[mtp.hpp](../packet93-packed-head2/mtp.hpp) lines 228 and 263–271, and
[rank.hpp](../packet93-packed-head2/rank.hpp) lines 128, 173 and 197.

| First-99 hit mean difference | Lane A | Lane B |
| --- | ---: | ---: |
| Draft compute-event sum | +0.021512 | +0.015166 |
| D minus draft compute-event sum | +0.352811 | −0.012897 |

The residual includes CPU work, copies, event gaps, queue waiting and
publication/polling. The retained event sum does not identify which of those
grew. It must not be called pure CPU overhead or proof of a slower draft
kernel. Source code still reads/dequantizes the embedding row, uploads it,
and copies hidden state inside D; these are useful future timing boundaries,
not measured causes here.

Inside Bh, `timings.jsonl` localizes most of its mean A-1 increase to
`wait_ms` (+0.154648 ms), with enqueue +0.018295 ms, retirement +0.010123 ms
and profiling-query work +0.002817 ms. On misses, the same rank's wait time
falls by 0.201195 ms. These are host-measured waits for work, not individual
target-head events. No retained event isolates the target head on card 1;
it could still be faster while the complete half gets slower.

**The gaps between commands do not explain the loss.** Median hit gaps:

| Screen | Emission → draft issue | Both inputs ready → rank1 half | Race end → emission | Total residual gaps |
| --- | ---: | ---: | ---: | ---: |
| A-0 | 0.005690 | 0.015048 | 0.001102 | 0.022081 |
| A-1 | 0.005621 | 0.015049 | 0.001092 | 0.021800 |
| A-2 | 0.005310 | 0.011847 | 0.000962 | 0.018219 |
| B-0 | 0.005290 | 0.011892 | 0.000981 | 0.018245 |
| B-1 | 0.005180 | 0.011932 | 0.000951 | 0.018094 |
| B-2 | 0.005260 | 0.011973 | 0.000992 | 0.018255 |

The JSON also retains miss gaps, rollback issue delay and restore-to-correction
delay. Its exact accounting check is algebraic: gaps are residuals. It checks
the join and arithmetic, but is not independent proof that all causes are known.

**Card identity and placement.** Screen identity, launch masks and the dominant
VRAM allocation in each rank's fdinfo agree:

| Lane | Rank 0: speculative/corrected half | Rank 1: target head and draft | CPU cores |
| --- | --- | --- | --- |
| A | physical card 0, `0000:23:00.0` | physical card 1, `0000:27:00.0` | `0-3,16-19` |
| B | physical card 2, `0000:43:00.0` | physical card 3, `0000:47:00.0` | `4-7,20-23` |

Lane B's filtered native index 1 is physical card 3. The `43:00.0` fault
history in [the stability guide](../../../../docs/host-stability-and-fault-diagnosis.md)
belongs to **B's rank 0**, not A's head card. All six retained kernel-window
logs contain no nonblank messages and all windows have empty stop reasons.
That excludes a recorded fault in these windows, not all possible hardware
effects.

The passive [current topology snapshot](host-topology.json) has one NUMA node,
all four devices reporting `numa_node=-1` and `local_cpulist=0-31`; this means
no per-device NUMA proximity is exposed. A descends from PCI root `pci0000:20`,
B from `pci0000:40`. Both ranks' saved process status permits memory node 0.
The stability guide documents Gen4 ×16 links. Negotiated link state during
these six screens was not retained; a later sysfs read cannot establish it.

**Logical allocations match between A-1 and B-1.** Rank-1 census, plans,
draft choices, draft tensor reads and all parity-0 prepared target arguments
are byte-identical between the two candidates. The target head virtual base
is **`0xffffeab18d200000`**, 2 MiB aligned, in **all six** runs. Candidate
logits input/output pointers also match across lanes. The argument decoding
uses [owner.cpp](../packet93-packed-head2/owner.cpp) lines 192–194 (IDs followed
by virtual pointers); logits is site 737. This rules out different target-head
virtual base alignment. Physical VRAM pages, bank placement and cache state
are not captured, so logical identity cannot exclude those effects.

The draft **does not read the transposed target layout**.
[mtp.hpp](../packet93-packed-head2/mtp.hpp) lines 105–109 and 176–185 keep
the expanded `p33.dense.segment` variant 6 and 91,392-row prefix. Production
shares the expanded target head; head-transpose allocates a separate expanded
prefix from the original weights. The six `draft-prefix.json` and
`draft-memory.json` receipts confirm that change in sharing.

| Rank-1 allocation, bytes | Production | Head-transpose |
| --- | ---: | ---: |
| Target output head | 839,321,600 | 521,472,000 |
| Additional expanded draft prefix | 0 | 308,904,960 |
| Complete device arena census | 31,267,162,826 | 31,258,218,186 |

The net arena saving is **8,944,640 bytes (8.53 MiB)**. The quoted DRM
27,054,116 KiB on A-1 versus 27,054,112 KiB on B-1 differs by just 4 KiB,
but those snapshots precede draft allocation:
[rank.hpp](../packet93-packed-head2/rank.hpp) line 243 records `after_load`,
then line 244 constructs `DraftRuntime`. The approximately 318 MB drop from
production therefore omits the new 309 MB prefix. Arena totals are tracked
live allocations, not a substitute measurement of full driver residency.

**Host pressure remains a confounder, not an established cause.** These
windows were not whole-host isolated. A-1's admission snapshot records clients
on B's cards, and its saved launch load average is 7.687 versus A-0's 3.133
and B-1's roughly 4.51. The brief also reports concurrent loading and archive
I/O. However, admission/last samples show approximately 118–121 GB available,
saved rank process status shows zero swap at that checkpoint, and the retained
first-99 half timings show no major page faults. These sparse samples do not
measure decode-time I/O stalls or D's page faults. They cannot prove or rule
out transient pressure. Bracketing controls help with drift, but do not make
the intervening host conditions identical.

**What the microbenchmark does and does not settle.** Both retained micro
runs used **card 2 / `43:00.0`**, which is neither screen's head-owning card.
The original run measured 1.416250 → 1.032084 ms, and the resealed repeat
1.416510 → 1.033281 ms. They used synthetic weights and 40 alternating pairs,
with exact FP32/BF16/argmax checks. This is good diagnostic evidence for that
isolated kernel on card 2; it cannot identify a card-1 target-head cost or
the complete engine's draft/queue interaction.

**Decision and next discriminating evidence.** Retain production for the
lane-A record lineage. Packet 97 may keep a separately labeled experimental
head-transpose composition, but B's positive source screen does not justify
putting that head into A's record configuration. This analysis does not alter
packet 97's existing source-selection rules or claim that any composite is
qualified. No speed or quality promotion follows from these 128-token screens.

The next authorized device study should measure card 1 and card 3 with the
same target-head microbenchmark, and separately compare the unchanged draft
prefix in shared-target versus separate-prefix allocations. Capture individual
head/prefix events, the full draft event span, copies, host preparation,
submission and publication waits, plus arena addresses and complete post-draft
DRM residency. Profiling is diagnostic and needs an overhead control before
using unprofiled engine timing for a verdict. Then run at least two fresh,
matched control/candidate/control engine brackets on A with comparable host
load, followed by B confirmation and the unchanged exact-output/acceptance
gates. A persistently slower isolated kernel would support a device/layout
effect; unchanged kernel times with a moving residual would point to queue,
transfer or host conditions. A target-only microbenchmark cannot resolve D.

**Reproduce the CPU analysis.** From the repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet93x-lane-analysis/analyze.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet93x-lane-analysis/analyze.py --check </dev/null
```

The script uses the standard library, caps address space at 4 GiB, imports
only packet 85's CPU accounting module, and writes only adjacent `analysis.json`.
`--check` writes nothing. It validates unique joins, original-versus-summary
receipt equality, all six output/guess sequences, the reported hit/miss
statistics, micro sample hashes, and the allocation/argument comparisons.
Source hashes bind the original evidence and the code used to interpret it.
The six screen trees are local evidence dependencies, not supplied by a clean
Git clone; preserve them at the paths and hashes listed in JSON. This is not
a publicly reproducible deployment recipe. Existing evidence was not modified.

Git's initial `pull --rebase` refused the pre-existing dirty tree. A fetch then
confirmed local main and origin/main were identical, so no stash or rebase
of unrelated work was needed. Only this new folder and the explicitly
requested new note are part of packet 93x.
