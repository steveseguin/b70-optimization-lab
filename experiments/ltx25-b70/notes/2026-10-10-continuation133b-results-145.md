# Packet 133b at 145 frames, and the corrected 169-frame census

The measured 145-frame line is exact and faster than 129. Of the three
169-frame proposals, only **split36 with the cone graph off and the native
display on xpu:3** clears the full conservative memory screen. Packet 134
prepares that arm for qualification. It is not expected to beat the 145 line.

This is a CPU-only analysis of saved receipts, not a new device measurement.
The [analyzer](../data/resume-20261008/continuation134-evidence-analysis.py)
and [frozen evidence](../data/resume-20261008/continuation134-evidence.json)
bind 144 input files by SHA256. They read no weights or runtime modules.
All commands use `nice -n 19`, `OMP_NUM_THREADS=2`, and
`/home/steve/.venvs/ltx25-baseline/bin/python -B`.

## Measured 145 budget

The source is the first 133b session, now archived under
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-continuation-stream-133b-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-gc60-ssbackground-sdc1-mi-cmtext-shift-textsplit36.completed-20261010T145013Z`.
The parent comparison is the saved 129 session 4 directory ending
`f145-gc60-ssbackground-sdc1-mi`, whose complete path and file hashes are in
the JSON. Run names' older `dxpu2` token is not display-placement evidence:
the actual decode records say display and audio xpu:3.

The owner's early figure is 5.213 seconds per six seconds of new video,
0.869 s/s, n=23; its reported even/odd medians are 5.17/5.25 seconds.
The original interval selection was not specified. For a reproducible
independent slice, this note fixes 23 differences from chunk7→8 through
chunk29→30. Commit-to-commit is 5.213306 seconds; submit-to-submit is
5.248350 seconds. These are different clocks, not interchangeable metrics.
Memory and parity use the separately fixed chunks0–30 inclusive. Timing
buckets below use chunks7–29 inclusive; their independent medians need not sum.

| Measured item | Median seconds | Scope |
|---|---:|---|
| Owner's early period | 5.213 | n=23, 6 s new video, 0.869 s/s |
| Fixed commit period | 5.213306 | 23 differences, 0.868884 s/s |
| Fixed submit period | 5.248350 | Same 23 differences, 0.874725 s/s |
| Submit through sampler A start | 0.444503 | Includes text on cuts, checks and snapshots |
| Sampler A kernel interval | 1.916740 | Nested within A bucket |
| A bucket through sampler B start | 2.185039 | Includes upscale and B conditioning |
| Sampler B | 1.668075 | B start to B done |
| Cone on chain | 0.748339 | Graph; owner's comparison to eager129 was about0.93 |
| Video done through anchor ready | 0.030038 | Anchor publication |
| Anchor ready through receipt staged | 0.071859 | Receipt publication |
| Full display | 2.814691 | Overlaps the next sampler; do not add to chain |
| Audio | 0.689880 | Serial decoder tail |
| Decoder queue wait | 0.000044 | Same fixed slice |
| Anchor ready through decode done | 4.239983 | Includes display/audio schedule |
| Hashes and diagnostics | 0.117823 | After decode |

Qualification verdict starts `94cd0653ca49`; the full SHA256 is in the
evidence. Its exact replay and all required checks passed. Every one of the
31 matched stream chunks equals 129 on stage-A, video and audio latents,
full decoded images, waveform, anchor and prompt hashes. Every cone agrees
with the display's last frame. This audit compares stored hashes; it does
not regenerate outputs or generalize exactness to untested prompts.

First cone capture, `qgraph-c000000`, records **3,806,330,880 bytes =
3.544921875 GiB** of reserved pool growth. The earlier temporal-squared
estimate was **4.505889893 GiB**, 0.960968018 GiB higher. The observed growth
is retained reservation growth, not an isolated instantaneous capture peak
or a proved upper bound. The 145 capture allowance remains 5 GiB.
Admission found 22,745,403,392 bytes =21.183307648 GiB free, against
14.75 GiB required, leaving 6.433307648 GiB. The owner's first-capture
request took about21 seconds; the receipt's submit-to-decode-done interval
is20.352532 seconds, distinct from pure capture time.

Physical free memory, GiB (2^30 bytes), fixed31 streaming receipts:

| Phase | xpu:0 | xpu:1 | xpu:2 | xpu:3 |
|---|---:|---:|---:|---:|
| Before | 9.422874 | 9.828781 | 5.038685 | 15.776173 |
| A-before / A-after | 9.454144 | 9.848331 | 5.038704 | 18.198067 |
| B-before / B-after | 9.270538 | 9.848309 | 4.907822 | 14.596481 |
| After | 9.301788 | 9.828781 | 4.907833 | 15.776173 |
| Minimum minus floor and0.75 band | 0.520538 | 1.078781 | 2.157822 | 4.846481 |

These columns are independent phase minima, not a simultaneous snapshot.
The JSON also retains all nine qualification rows' separate phase minima.
The unchanged conservative floors are8/8/2/9 GiB. The smallest snapshot
margin is **1,364,230,144 bytes =1.270538330 GiB on xpu:0**, at B-before
and B-after, not on the decode card. There are **8 dual snapshots out of182**;
every dual comparison agrees. Full four-card snapshots remain enabled.

The coordinator subsequently stopped this session after73 chunks for a
storage accounting refusal involving a multiply linked file. CURRENT records
the separate packet135 investigation. This fixed early window does not claim
a completed stability run, and packet134 does not repair that unrelated guard.

## Corrected 169 census

Split36 puts text layers0–35, **15.228121 GiB**, plus4.125905 GiB of other
primary text state on xpu:2. The measured xpu:2 low is only4.907822 GiB free
at145; adding the display replica here is no longer plausible. The text
inventory and graph-storage distinctions are in the
[133 memory evidence](2026-10-10-continuation133-memory-evidence.md).

For cards0/1/2, use the measured145 minimum and subtract the prior123b
145→169 physical-free losses of0.094734192/0.050109863/0.002517700 GiB.
These historical losses are a planning scenario across different residency,
not a new169 peak measurement. All remain above their floor plus0.75.

For card3, use a consistent admission boundary: the minimum of the three
133b `qeager` decode records' `xpu3_free_before_decode`,
**21.111042023 GiB**. The serial worker reads this immediately before native
decode with the cone graph off. It may include retained allocator storage;
it is not a claim that every pool has been released. Charge the entire
**6.5 GiB169 display reserve**. For graph arms, also charge **6.704 GiB**,
rounded upward from the unchanged145 allowance `5*(22/19)^2`. The smaller
4.752748 GiB extrapolation from observed145 retained growth is not a169
peak bound, so it cannot replace that allowance. No allocator release is
credited. The6.5 display allowance is inherited planning evidence, not a
measured isolated native169 transient.

| 169 arm | Card0 margin | Card1 | Card2 | Card3 | Decision |
|---|---:|---:|---:|---:|---|
| a. Cone graph, native display3 | +0.425804 | +1.028671 | +2.155304 | **−1.842958** | Refuse |
| b. Cone graph, display replica2 | +0.425804 | +1.028671 | **−5.121668** | +4.657042 | Refuse |
| c. Cone graph off, native display3 | +0.425804 | +1.028671 | +2.155304 | **+4.861042** | Prepare qualification |

All margins are GiB **after floor plus0.75 GiB screening**, and after the
applicable full reserve. Arm b charges834,267,746 bytes of replica weights
and6.5 GiB reserve to card2. Its card3 cell describes steady placement;
qualification still exercises the full original decoder. Charging that
reference reserve simultaneously lowers card3 to−1.842958 as well. The
card2 refusal alone already closes this arm.

Arm c also passes a deliberately stronger envelope. The minimum across
**every phase of all three qeager receipts is17.154560089 GiB** on card3.
Subtracting the entire6.5 GiB display allowance again, with no credit for
already retained display allocations, leaves **+0.904560089 GiB** above
floor plus band. Packet134 nevertheless checks fresh physical free before
every full display decode: at least16.25 GiB before, and9.75 GiB after.
A failed check refuses the arm; there is no fallback or smaller reserve.

The initial planning calculation was wrong: starting from a measured145
post-display snapshot and subtracting only `6.5−5.640625` treats the snapshot
as if it already charged the whole145 reserve. It did not. That produced a
false positive of about+0.828 GiB for arm a. The corrected analysis above
charges full reserves at an explicit admission boundary. The intermediate
analysis output is retained as development evidence, never as admission.

## Timing forecast and display completion

These are engineering estimates, not measured169 results or public benchmark
points. Prior123b169 measured about6.82 s per7 s, sampler A/B1.98/1.85 s,
eager cone work1.14 s but1.73 s on chain, and full display3.98 s. Its extra
queue wait mostly followed display, while audio/diagnostics still occupied
the serial worker; see the
[123b169 analysis](2026-10-10-continuation123b-results-169.md).

| Arm | Predicted period for7 s video | Predicted s/s | Memory |
|---|---:|---:|---|
| a. Graph cone about0.9 s, native display3 | 6.25–6.70 s | 0.893–0.957 | Refused |
| b. Graph cone, replica2 | 6.00–6.50 s | 0.857–0.929 | Refused; hypothetical scheduling benefit |
| c. Eager cone, native display3 | **6.50–6.95 s** | **0.929–0.993** | Candidate; center6.65 s /0.950 |

Replacing145 sampler/cone timings alone would suggest about5.61 s for the
graph chain. The serial worker instead needs about0.90 cone +0.56 anchor/go
+0.16 B preparation +3.98 display +0.69 audio +0.12 diagnostics =6.41 s.
The eager arm adds about0.24 s. This retains queue contention; it does not
blindly subtract the old0.59 s wait. Display completes approximately
0.56+0.16+3.98 =**4.70 seconds after anchor readiness**, inside the projected
period. The later audio/record tail still limits throughput. A buffer cannot
substitute for this completion requirement.

To beat145's5.213/6, a169 period must be below**6.081833 s**. Arm c is not
forecast to do that. It is prepared because it clears the requested memory
screen, with native exactness, actual memory plateau, display deadline and
sustained cadence still required before a coordinator can judge it.
