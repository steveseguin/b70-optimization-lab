# Packet 123b at 169 frames: the queue is after display, and legacy placement now fits on paper

169 is byte-exact, but does not beat the 145-frame line. The coordinator measured
6.824 seconds per seven seconds of new video (0.975 s/s), against 145's 5.73
seconds per six (0.955). The complete saved timeline identifies a more specific
bottleneck than “the cone waits behind the display”: **in 37 of 38 completed
interior intervals the display has already finished when the next cone is queued;
the one decode worker is still finishing audio, diagnostics and its record.**
The one exception has only 15 ms of display left. Moving the display to xpu:2
without releasing that worker cannot by itself remove the measured queue wait.

The smallest admissible placement is **legacy auxiliaries, eager display replica
on xpu:2, dg0**, with the previous chunk's audio moved earlier into the successor sampler
window, then a bounded display/finishing handoff that frees the cone worker. Both auxiliary owners on xpu:1
fail the 0.75 GiB screening margin even before any new workspace. These are CPU
planning findings, not a device qualification or a measured speed improvement.

## Reproduction and sample boundaries

The [standard-library analysis](../data/resume-20261008/continuation124-evidence-analysis.py)
and [frozen output](../data/resume-20261008/continuation124-evidence.json) bind
531 regular files/observed file snapshots by SHA256, including completed receipts,
old census data, decode records and the two saved client work directories. They
read no model payload and import no runtime. All Python commands used
`/home/steve/.venvs/ltx25-baseline/bin/python -B`, with at most four OpenMP threads.

169 run: `encoder-server-continuation-stream-123b-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f169-auxxpu2`.
145 comparison: the corresponding `f145-auxxpu2.completed-20261010T063121Z`.
Both use aux xpu:2 and actual display xpu:3; the older `dxpu2` filename segment
is not the display placement authority. Parent manifest is
`5bdc0956f69259a99ca82849280e73b8bd2a80e28ff421ce5d61122e8a74d433`.
169 freeze verdict is
`4eeb3b603c9497f3105ccca65ffce0aeab29ceacedcf97067a33eb07b26bd08a`.
All 49 saved 169 decodes, and all 41 saved 145 decodes, have `cone_equal=true`.
The freeze reports three-chain identity; this CPU analysis did not rerun it.

Memory uses every saved streaming receipt: 169 sequences 0–48 and 145 0–40.
The detailed 169 timing table fixes 10→11 through 47→48, 38 intervals; its
submit-to-next-submit median is **6.874853 s (0.982122 s/s)**, mean 6.988409 s.
145's 10→11 through 39→40, 30 intervals, give **5.837998 s (0.973000 s/s)**,
mean 5.939118 s. These completed-session slices remain slower at 169.
The coordinator's earlier 27/23-period values remain attributed to that earlier
snapshot: its exact selected interval set is not retained in the prose note.
A fixed 169 sequence 10–36 slice reproduces the quoted kernel and queue medians,
but gives a 6.914584 s submit-to-next-submit period; fixed 145 10–32 gives
5.943812 s. Do not silently claim these are the identical period sample.

## What the xpu:3 timeline actually shows

For 169 sequences 10–36 (27 paired chunks), times below are medians relative to
the **next chunk's submit**. Medians describe separate distributions and need
not add exactly.

| Event | Seconds |
|---|---:|
| Previous display starts | 0.714 |
| Previous display finishes | 4.704 |
| Next cone is queued | 4.742 |
| Previous decode record is staged | 5.266 |
| Next cone starts | 5.319 |
| Next cone finishes | 6.469 |

Every one of those 27 cone enqueues occurs after the previous display ends.
In the larger completed 38-interval sample, chunk 42→43 has 0.015261 s of
display remaining at enqueue; the other 37 have none.
There is zero overlap between the recorded display interval and next cone
execution. The cone's actual work is **1.137716 s**, versus **1.019900 s** at 145;
its on-chain interval is **1.729972 s**, versus **1.024533 s**. The extra
approximately 0.705 s therefore comprises approximately **0.592 s FIFO wait**
and **0.118 s extra cone execution**, with small entry differences. The 169
post-display audio/hash/record interval is **0.554901 s**, then another **0.063235 s**
passes before the worker starts the next job. At 145 the post-display tail is
0.411707 s and finishes about half a second before the next cone is ready;
its median FIFO wait is just 45 microseconds.

The coordinator's “go-wait 1.06” is `anchor_ready_to_go` (1.056907 s), including
commit and A preparation. The actual wait for the successor sampler-A event is
**0.288190 s** median. It is not one second of idle wait that can simply be removed.

Full safety snapshots remain real all-card synchronizations. For example, next
chunk 11 has B-before at 2.636–2.696 s and B-after at 2.765–2.826 s while the
previous display runs 0.707–4.690 s. A barrier drains work already submitted;
it cannot finish future tiled operations that the decoder's Python loop has not
submitted. A separate worker may still move waiting into these barriers or into
text work on xpu:2. The forecast therefore does **not** blindly subtract every
FIFO second. No safety barrier should be removed to obtain a speed number.

## The three-second bound

`integration.py:GO_BOUND_S=3.0` bounds waiting for the successor sampler A
(and shares a deadline with the optional sampler-B release). It **does not**
bound the display decode's execution. A 3.98-second display does not time out,
abort, reset, or latch merely for exceeding three seconds. It extends the decode
worker's service time and can put its successor into the FIFO. All 48 nonfinal
169 chunks record `sampler-a-start`; final chunk 48 records `bound` after the
client stopped submitting. That is the intended finite end-of-stream wait.
The earlier “3 s off-chain bound” is thus a planning target, not an execution
watchdog. The same interpretation is already stated in the 123 design note.

## Decoder scaling: measured frames and seconds

Periods divide by **new anchored video**, excluding the repeated first frame.
The 97/121 rows use the exact prior 100-interval census; the 145 legacy row uses
40. Graph, replica, auxiliary placement and session differ; these rows are
comparisons, not a controlled four-point kernel scaling law.

| Arm | Frames | New video seconds | Actual cone s | Cone on chain s | Full display s |
|---|---:|---:|---:|---:|---:|
| 117 graph | 97 | 4 | 0.686 | 0.691 | 1.554 |
| 118b eager | 121 | 5 | 0.929 | 0.978 | 2.683 |
| 120 graph cone, eager replica | 121 | 5 | 0.765 | 0.770 | 2.681 |
| 121 eager, legacy | 145 | 6 | 0.869 | 0.875 | 2.719 |
| 123b eager, auxiliary xpu:2 | 145 | 6 | 1.020 | 1.025 | 2.743 |
| 123b eager, auxiliary xpu:2 | 169 | 7 | 1.138 | 1.730 | 3.983 |

145→169 adds 16.55% total frames / 16.67% new video. Actual cone grows 11.6%,
full display 45.2%. The 0.7-second on-chain jump is consequently **not a cone
kernel scaling measurement**. Full display exceeds the forecast 2.72–3.30 s by
0.683 s even at its high end. Tiled boundary/shape effects and scheduling are
possible explanations; these wall timestamps cannot isolate them. The
last-frame cone's kept dependency does not grow in proportion to all frames.
Sampler A/B remain about 1.982/1.849 s at 169, which keeps longer chunks worth
trying after the serial tail is removed.

## Memory: phase minima and measured peaks

These are phase-boundary physical-free samples. Allocator high-water is cumulative,
not a reset per-kernel peak. No receipt gives isolated cone/display/upsampler
workspace peaks. GiB means 2^30 bytes; the coordinator's 1.93 GB means decimal.
The unchanged conservative card floors are 8/8/2/9 GiB. Measured 169 minimum
snapshot margin is 1,930,596,352 bytes = **1.798008 GiB**, on xpu:1.

| Frames / phase, free GiB | xpu:0 | xpu:1 | xpu:2 | xpu:3 |
|---|---:|---:|---:|---:|
| 145 prepared | 11.898624 | 10.574406 | 10.569115 | 15.180622 |
| 145 before | 10.463909 | 9.848133 | 10.184406 | 11.381393 |
| 145 A | 10.463905 | 9.848137 | 10.389484 | 15.242725 |
| 145 B | 10.362324 | 9.848118 | 10.106262 | 11.438019 |
| 145 after | 10.463890 | 9.848122 | 10.389469 | 11.381382 |
| **145 margin above floor** | **2.362324** | **1.848118** | **8.106262** | **2.381382** |
| 169 prepared | 11.898632 | 10.574413 | 10.569118 | 15.180622 |
| 169 before | 10.382835 | 9.798031 | 10.105713 | 11.148956 |
| 169 A | 10.382858 | 9.798031 | 10.388920 | 15.242714 |
| 169 B | 10.267590 | 9.798008 | 10.103745 | 11.193867 |
| 169 after | 10.382843 | 9.798012 | 10.388905 | 11.148949 |
| **169 margin above floor** | **2.267590** | **1.798008** | **8.103745** | **2.148949** |

| 169 cumulative allocator high-water, GiB | xpu:0 | xpu:1 | xpu:2 | xpu:3 |
|---|---:|---:|---:|---:|
| allocated | 19.360769 | 20.527616 | 17.804817 | 13.881492 |
| peak | 19.686969 | 20.817396 | 18.073120 | 16.553885 |
| reserved | 20.181641 | 21.367188 | 20.423828 | 19.699219 |

The packet-123 projections for 169 were **1.620–1.930 / 1.574–1.711 /
6.439 / 0.825–1.557 GiB**. Actual phase-sampled margins are **2.268 / 1.798 /
8.104 / 2.149 GiB**. The xpu:2 forecast had additionally reserved 2 GiB of
auxiliary workspace; sampled free is not the same quantity as that reserved
planning margin. Sampler and video-card readings nevertheless leave materially
more room than the pessimistic scaling estimate. Dual snapshots remain periodic:
14/290 snapshots at 169 and 14/242 at 145, including startup periodic inspection;
minimum margins are far above the 0.5 GiB near-floor trigger.

## Packet 124 alternatives and admission arithmetic

The static census remains the 123 safetensors/header inventory: upsampler
**0.927351236 GiB**, audio VAE+vocoder **0.339622486 GiB**, combined
**1.266973723 GiB**. No precision, schedule arithmetic or model weight is changed.
All rows below retain measured reservation tails; none credits the disappearance
of the full xpu:3 display workspace. A 0.75 GiB margin is still required above
unchanged 8/8/2/9 floors. These are engineering scenarios, not guaranteed peaks.

| 169 candidate | xpu:0 margin | xpu:1 margin | xpu:2 margin | xpu:3 margin | Decision |
|---|---:|---:|---:|---:|---|
| (a) Both auxiliaries →1; display replica →2 | 2.268 | **0.531 before workspace** | 2.210 after 6.5 reserve | 2.149 | Refuse: 1 fails before workspace |
| (b) Legacy auxiliaries; display replica →2 | **1.340** | **1.798** | **2.210 after 6.5 reserve** | **1.809** | Smallest memory-admissible placement; native gate pending |
| (c) Aux →2, same-card split/deferred display | 2.268 | 1.798 | 8.104 measured, 6.104 after 2 workspace reserve | 2.149 | Memory fits; scheduling/latency unsupported |

For (a), charging the inherited 2 GiB auxiliary workspace above the sampler
floor takes xpu:1 to **−1.469 GiB**. Even a smaller allowance cannot repair its
static shortfall. The observed 145 xpu:1 margin 1.848 yields only 0.581 after
both owners, also below 0.75. Do not infer safety from “about 1.8 GiB free”
without subtracting the complete owner footprints and the card's own floor.

For (b), legacy 169 xpu:0 is the new measured 2.267590 minus 0.927351 =
**1.340238 GiB**, and xpu:3 is 2.148949 minus 0.339622 = **1.809326 GiB**.
These static-only counterfactuals supersede the old 145→169 extrapolation for
planning, not as a claim that legacy169 has been measured. At 145 the actual
legacy reference is **1.270 / 1.828 / 3.070 / 1.850 GiB**, where card2 includes
its default 5.640625 GiB replica reserve. The new 169 estimate has 0.590 GiB of
room above the 0.75 requirement on its tightest card. Restoring upsampler/audio
may alter retained allocator/storage behavior; the first real readings must
confirm it.

The measured 121 replica's maximum peak-or-reservation growth is
**2.982421875 GiB**; its 169 linear/quadratic latent-frame scenarios are
**4.100830–5.638641 GiB**. 169 therefore recommends
**`LTX_DISPLAY_REPLICA_TRANSIENT_GIB=6.5`**, leaving 0.861359 GiB over the high
scenario. This is already the inherited 169 default, so the explicit option
documents the census; no increase is required. Reusing the 145 allowance
5.640625 at 169 would leave only 0.001984 GiB and is refused by the length floor.
145 can retain the
5.640625 default against its **3.541626–4.205681 GiB** scenarios. This is still
scaled from a measured 121 transient, not a fabricated isolated 169 peak.
The 169 cumulative xpu:3 peak cannot replace a replica-specific measurement.

The conservative xpu:2 starting point is the **measured repeated before-decode
minimum 10.710304 GiB** in packet120, already including replica weights and text
coexistence; do not subtract the 0.776972 GiB copy twice. Subtracting 6.5 and the
2 GiB floor leaves 2.210304. Its measured after-decode minimum was 7.728 GiB,
with about 2.982 GiB additional reservation; later before-decode readings recovered.
That recovery is evidence about the old serialized runtime, not a promise for a
new concurrent schedule. Keep the before-copy, after-copy, **every before-decode**,
after-decode and measured-growth guards. If reservations persist and the next
before-decode budget refuses, that is a closed native result, not permission to
shrink the reserve, change a floor, flush host caches or silently fall back.

For (c), splitting a decoder call needs exact operation/rounding order and
explicit yield boundaries in the native decoder. Merely chopping frame tensors
can change causal context and kernel shapes, and is not an exact solution.
Deferring all display until the next cone finishes moves its start from roughly
successor-submit+0.714 to +5.9–6.5 s. It adds **about 5.2–5.8 s sink latency**;
previous-anchor→display-complete then becomes roughly **10–11 s**, exceeding
the seven-second chunk budget. Although a deep buffer could still consume one
chunk every period, that fails the requested completion-within-period constraint.
A two-part exact submission schedule might do better but has no measured safe
split point here. It is not the smallest complete CPU change.

## Forecast and required gates

Moving display alone while keeping one serial worker: **6.65–7.15 s at 169 =
0.950–1.021 s/s**; no reliable win over the measured 145 line is predicted.
The selected placement plus optional parallel display and **early audio**
forecasts **6.20–6.65 s = 0.886–0.950 s/s**, central about **6.30 s / 0.900 s/s**.
This requires finishing audio on xpu:3 immediately after B preparation, while
the successor sampler is still running on 0/1, before handing the replica
display to its worker. Simply splitting the old tail without moving audio
would leave the shared encoder lock occupied when the next cone is ready: it
could save only the approximately 0.19 s hash/record/hand-off tail. Early audio
instead shifts replica display from successor-submit+0.71 to about +1.14 s;
it finishes around +5.12 s while the next cone can begin around +4.74 on the
other card. No decoder kernel speedup is assumed. Text/card contention, moved
barriers or record joins can instead yield **6.65–7.20 s = 0.950–1.029 s/s**.
The estimated previous-anchor→display-complete cost is
1.06 go/preparation + 0.15 B preparation + 0.43 audio + 3.98 display = **5.62 s**,
under the 7 s period. Hashes and an approximately 0.8 s MP4 stage make about
6.55 s to the sink, still under 7 s in this scenario. These are scheduling
projections, not guaranteed deadlines. The early audio waveform is about
2.57 MiB on CPU; no extra device waveform/workspace residency is assumed. At 145 forecast
**5.50–6.10 s = 0.917–1.017 s/s**: it currently has effectively no FIFO wait to
remove. These are forecasts, not measured points or public performance claims.
To beat 145's coordinator 0.955 line at 169 requires **period <6.685 s**;
to beat the older 0.939 line requires **<6.573 s**. Keep both thresholds visible.

Coordinator recommendation, text only: qualify 145 dg0 legacy plus eager xpu:2
replica first; compare output to the saved same-length chain and examine actual
per-card memory, full snapshots and record joins. Then qualify 169 with 6.5 GiB
reserve and compare the frozen same-length outputs where compatible, plus the
full three-chain identity gate. Require the replica weight-copy bitwise test,
full-image cross-card comparison in qualification, and **every streaming chunk's
cross-card display last-frame == cone byte check**. A last-frame comparison alone
is not a full-image quality gate. Demand ordered, bounded, once-only records,
complete final-chunk drain, failure propagation and no hidden fallback from any
new worker. A sustained cadence check and fresh repeat decide the speed verdict.
No device work or live operational instruction was executed in this analysis.

Open: true isolated phase peaks, 169 replica transient and retained reservations,
legacy169 measured admission, new-worker races/barrier effects, full model
cross-card identity and sustained/repeated speed. A CPU fake cannot close these.

## Per-chunk xpu:3 timeline

All timestamps below are seconds relative to the **successor submit**. “Record”
is the predecessor decode record staging point. “Queue” is the successor cone
enqueue. “Cone” is successor cone start/end. Detailed absolute nanoseconds,
go-event wait, anchor-to-go, FIFO and source hashes remain in the linked JSON.
These are host operation timestamps, not profiler kernel launch timestamps.

| Chunk→next | Display start–end | Queue | Record | Cone start–end | Next FIFO | Go event wait / anchor→go |
|---|---:|---:|---:|---:|---:|---:|
| 10→11 | 0.707–4.690 | 4.705 | 5.247 | 5.300–6.435 | 0.595 | 0.273 / 1.079 |
| 11→12 | 1.095–5.068 | 5.128 | 5.620 | 5.682–6.865 | 0.554 | 0.653 / 1.192 |
| 12→13 | 0.708–4.692 | 4.730 | 5.243 | 5.295–6.430 | 0.565 | 0.290 / 1.053 |
| 13→14 | 0.726–4.715 | 4.748 | 5.266 | 5.319–6.469 | 0.571 | 0.276 / 0.805 |
| 14→15 | 0.664–4.669 | 4.690 | 5.232 | 5.288–6.423 | 0.598 | 0.279 / 1.045 |
| 15→16 | 1.164–5.108 | 5.140 | 5.666 | 5.737–6.930 | 0.597 | 0.679 / 1.230 |
| 16→17 | 0.682–4.665 | 4.691 | 5.223 | 5.286–6.409 | 0.596 | 0.269 / 1.032 |
| 17→18 | 0.679–4.646 | 4.669 | 5.207 | 5.270–6.394 | 0.601 | 0.259 / 0.741 |
| 18→19 | 0.718–4.726 | 4.737 | 5.280 | 5.346–6.482 | 0.609 | 0.308 / 1.062 |
| 19→20 | 1.360–5.402 | 5.531 | 5.965 | 6.024–7.191 | 0.492 | 0.814 / 1.405 |
| 20→21 | 0.749–4.764 | 4.785 | 5.324 | 5.392–6.546 | 0.606 | 0.318 / 1.156 |
| 21→22 | 0.749–4.738 | 4.764 | 5.296 | 5.366–6.513 | 0.602 | 0.288 / 0.849 |
| 22→23 | 0.714–4.689 | 4.718 | 5.241 | 5.305–6.454 | 0.587 | 0.293 / 1.057 |
| 23→24 | 1.093–5.088 | 5.107 | 5.652 | 5.719–6.886 | 0.613 | 0.655 / 1.169 |
| 24→25 | 0.710–4.675 | 4.755 | 5.228 | 5.291–6.408 | 0.536 | 0.286 / 1.056 |
| 25→26 | 0.755–4.738 | 4.762 | 5.301 | 5.363–6.489 | 0.602 | 0.296 / 0.788 |
| 26→27 | 0.678–4.704 | 4.713 | 5.269 | 5.343–6.486 | 0.630 | 0.272 / 1.009 |
| 27→28 | 1.023–4.994 | 5.065 | 5.548 | 5.617–6.792 | 0.552 | 0.663 / 1.147 |
| 28→29 | 0.712–4.672 | 4.757 | 5.224 | 5.293–6.414 | 0.536 | 0.285 / 1.070 |
| 29→30 | 0.688–4.658 | 4.698 | 5.213 | 5.283–6.423 | 0.585 | 0.275 / 0.765 |
| 30→31 | 0.695–4.731 | 4.742 | 5.283 | 5.352–6.485 | 0.610 | 0.273 / 1.051 |
| 31→32 | 1.115–5.084 | 5.117 | 5.638 | 5.699–6.882 | 0.582 | 0.688 / 1.192 |
| 32→33 | 0.737–4.699 | 4.738 | 5.252 | 5.314–6.438 | 0.577 | 0.312 / 1.115 |
| 33→34 | 0.709–4.674 | 4.708 | 5.228 | 5.291–6.438 | 0.583 | 0.281 / 0.784 |
| 34→35 | 0.685–4.665 | 4.690 | 5.219 | 5.283–6.428 | 0.594 | 0.283 / 1.062 |
| 35→36 | 1.119–5.103 | 5.128 | 5.666 | 5.720–6.882 | 0.592 | 0.667 / 1.198 |
| 36→37 | 0.688–4.674 | 4.705 | 5.226 | 5.288–6.450 | 0.583 | 0.270 / 1.034 |
| 37→38 | 0.713–4.694 | 4.721 | 5.254 | 5.319–6.463 | 0.598 | 0.265 / 0.760 |
| 38→39 | 0.699–4.703 | 4.735 | 5.278 | 5.347–6.492 | 0.612 | 0.293 / 1.044 |
| 39→40 | 1.442–5.596 | 5.617 | 6.153 | 6.214–7.392 | 0.597 | 0.858 / 1.508 |
| 40→41 | 0.739–4.733 | 4.755 | 5.294 | 5.363–6.512 | 0.608 | 0.313 / 1.203 |
| 41→42 | 0.808–4.852 | 4.855 | 5.407 | 5.479–6.640 | 0.624 | 0.312 / 0.875 |
| 42→43 | 0.678–4.724 | 4.709 | 5.275 | 5.331–6.488 | 0.622 | 0.277 / 1.034 |
| 43→44 | 1.128–5.114 | 5.148 | 5.662 | 5.732–6.890 | 0.584 | 0.657 / 1.190 |
| 44→45 | 0.703–4.681 | 4.712 | 5.233 | 5.295–6.440 | 0.583 | 0.284 / 1.091 |
| 45→46 | 0.757–4.769 | 4.809 | 5.328 | 5.400–6.558 | 0.591 | 0.293 / 0.821 |
| 46→47 | 0.710–4.761 | 4.764 | 5.329 | 5.401–6.576 | 0.637 | 0.283 / 1.069 |
| 47→48 | 1.171–5.178 | 5.197 | 5.739 | 5.809–6.976 | 0.612 | 0.728 / 1.231 |
