# Packet 121 CPU census: longer chunks

CPU regular-file analysis only. [Evidence JSON](../data/resume-20261008/continuation121-evidence.json)
records SHA256 for 747 read-only source files, including saved receipts and observed
live-manifest bytes. No runtime import, device query, endpoint or service operation
was used. These estimates are planning scenarios, not measurements at a new length.

**Recommend 145 frames, dg0, display on xpu:3 first. Do not admit 169 frames yet.**
The 145-frame dg0 estimate preserves all measured floors with useful room. The
169-frame conservative sampler envelope exceeds the xpu:0 floor by about 0.095 GiB.
A display replica cannot fix sampler-card pressure. Neither graph-pool growth nor
replica relief is known at the longer shape.

## Receipt census

Interior means stream sequence at least 10. The saved dg0 session has 261 interior
receipts; dg1 sampler-a has 27; packet 119 dg1 eager-display has 51. The first two
are the saved 118b runs; 119 separates the eager display and retained graph pool.
The original 118b manifests at `s118b-live01`, `s118b-live02`, `s118b-live03` and
`s118b-dg1-live01` were read only. File hashes bind exactly the bytes observed.

| Device | dg0 preparation free, bytes | dg0 minimum sampled free, bytes | Required floor |
|---|---:|---:|---:|
| xpu:0 | 11,773,632,512 | 10,035,761,152 | 8 GiB before request/conditioning |
| xpu:1 | 11,354,193,920 | 10,621,870,080 | 8 GiB before request/conditioning |
| xpu:2 | 12,709,572,608 | 12,569,018,368 | 2 GiB |
| xpu:3 | 15,947,759,616 | 12,683,943,936 | 9 GiB before decode/conditioning; 2 GiB after |

Minima include before/after request and A/B conditioning readings. Before-cone
xpu:3 minimum is 15,640,940,544 bytes in dg0, 12,842,647,552 in dg1 sampler-a,
and 12,846,866,432 in 119. During display overlap xpu:3 reaches 10,424,623,104
bytes in dg1 sampler-a and 9,956,974,592 in 119. These sites do not continuously
sample kernel peaks. The 119 latter value is only 293,298,176 bytes above 9 GiB;
extra dual safety inspections must remain when their threshold is reached.

The upsampler is on **xpu:0**. Sampler activations/captured routes are on xpu:0/1.
Stage-B VAE encoding and the cone are on xpu:3; encoding a single anchor does not
add temporal input frames when the chunk grows. Display is on xpu:3 by default
or on the optional decoder-only xpu:2 replica. Text work still occupies xpu:2
and xpu:3. The image decode and audio decode share xpu:3 in the inherited order.

There is no isolated upsampler/cone/display peak trace in these receipts. On
xpu:0 the preparation-to-minimum-free loss is 1,737,871,360 bytes; on xpu:1 it is
732,323,840. Treat those entire losses as the sampler/route/upsampler allowance,
including retained allocations, rather than inventing separate additive peaks.
The dg0 xpu:3 equivalent loss is 3,263,815,680 bytes, covering cone, display,
encode, audio and retained allocations. Its observed peak-allocation-above-idle
envelope is 2,404,414,464 bytes; it is an aggregate, not an isolated display peak.
A single decode worker means current cone and previous full display are ordered;
their peaks need not be summed as simultaneous, but retained storage remains.

The dg1 cap `1.0` means 1,000,000,000 bytes of post-capture admission, **not** a
hard bound. The observed first capture retains 3,430,940,672 bytes. For 119,
subtracting that from its full preparation-to-minimum-free loss leaves a
2,559,827,968-byte non-pool pressure envelope. A new temporal shape may grow the
first capture. No floor or inspector threshold is reduced to make it fit.

## Explicit memory scenarios

Let `r=latent_frames/16`: 19/16 at 145, 22/16 at 169. For sampler-card and dg0
xpu:3 physical-free losses, bracket growth from `r` to `r*r`. These are linear
and quadratic planning scenarios, **not proven upper bounds or confidence
intervals**. They deliberately include more than live activations. For dg1,
bracket the first capture from constant to `r` and the remaining 119 pressure
from `r` to `r*r`.

The replica copies 834,268,000 checkpoint bytes (decoder plus statistics), no
encoder and no graph pool. On xpu:2 use the measured low free reading, then
subtract those bytes and the packet-120 4 GiB transient allowance scaled by
`r..r*r`: 4.75–5.64 GiB at 145, 5.50–7.56 GiB at 169. These larger planning
allowances must not be described as the current fixed 4 GiB runtime guard.
Before-copy, before-decode and after-decode physical checks remain required;
only actual qualification can establish a sufficient native allowance.

Margins below are **GiB above the unchanged floor**, not free GiB. Negative
values mean refusal in that scenario.

| Device/configuration | 145 frames margin | 169 frames margin |
|---|---:|---:|
| xpu:0, every configuration | 0.683–1.043 | **−0.095–0.740** |
| xpu:1, every configuration | 1.613–1.765 | 1.285–1.637 |
| xpu:2, no replica, dg0 or dg1 | 9.706 | 9.706 |
| xpu:2, replica, dg0 or dg1 | 3.288–4.179 | 1.366–3.429 |
| xpu:3, dg0, no replica | 1.566–2.243 | 0.106–1.673 |
| xpu:3, dg1 cap 1.0, no replica | **−1.304–−0.174** | **−3.048–−0.621** |
| xpu:3, dg0, replica, retained-reference to optimistic relief | 1.566–4.902 | 0.106–4.752 |
| xpu:3, dg1 cap 1.0, replica, retained-reference to optimistic relief | **−1.304–2.485** | **−3.048–2.458** |

For the two replica xpu:3 rows, the lower end gives **no credit** for moving
full display: the mandatory xpu:3 eager qualification reference can leave its
allocations reserved. The intentionally loose optimistic end removes the whole
2,404,414,464-byte aggregate envelope before scaling the remainder. That is an
upper estimate of possible relief, not proof all those bytes belong to display.
The range cannot establish safe dg1 admission. The 2 GiB post-decode floor is
less restrictive than the 9 GiB pre-decode/encode floor used for these margins.

These numbers support a measured 145 dg0 first arm. They do not justify enabling
169 merely because the optimistic linear case fits. Measure 145 all-card peaks,
minimum physical free, pool growth and text-turn overlap first; reopen 169 from
that evidence. A positive estimate does not override runtime refusal.

## Timing without counting the same cost twice

The historical 117 values 3.22 → 3.46 seconds are **sampler-A bucket plus sampler
B**; A's bucket includes upsample and B preparation. They are not isolated
sampler kernels. In addition, 97 uses dg1 and 121 uses dg0, so the apparent
0.01 seconds/frame slope is only a planning clue, not a controlled length slope.

The 118b dg0 saved 100 intervals, sequence 10 through 109, give:

| Per-chunk quantity | Median seconds |
|---|---:|
| Submit to next submit | 5.296904 |
| Pure sampler A + B | 3.182548 |
| Sampler A bucket + B | 3.470927 |
| Cone on chain | 0.986260 |
| Period minus A-bucket/B/cone, computed per chunk | 0.846973 |
| Period minus pure sampler/cone, computed per chunk | 1.129302 |

The residual already includes submit, snapshots, handoff, receipt and turnaround
where they lie on the chain. Do not add the whole 0.36-second snapshot total to
0.50-second submit plus B preparation and then add receipt again. Medians also
do not add exactly. The user's rough 6.1-second estimate is a useful high case,
but adding all those overlapping buckets overstates the central estimate.

For central 145, start from 5.2969 and add about 0.24 for the historical
sampler-bucket slope, 0.13 for cone growth and 0.08 for FIFO/guard uncertainty:
**about 5.75 s**. For 169, add 0.48, 0.30 and 0.22: **about 6.30 s**. The cone's
last-frame dependency is finite, but its native first stage still processes the
whole latent; neither constant cost nor full linear savings are guaranteed.

| dg0/xpu:3 planning case | Period | Work/nominal video second | Work/new anchored video second |
|---|---:|---:|---:|
| 145 frames | **5.55–6.10 s**, central 5.75 | **0.919–1.010** | **0.925–1.017** |
| 169 frames, geometry-only candidate | **6.00–6.75 s**, central 6.30 | **0.852–0.959** | **0.857–0.964** |

The nominal denominators are 145/24 and 169/24. Anchored chunks drop one frame,
so sustained new-video thresholds are **6.0 and 7.0 seconds**. Thus 145 can
plausibly cross real time but its range does not promise it. The 169 prediction
is conditional on a future admitted memory configuration, not permission to run.

Full eager display scales from about 2.70 seconds to roughly 3.2–3.5 at 145 and
3.7–4.3 at 169; audio, encode preparation, hashing and preview are also larger
or still occupy the ordered worker. New FIFO waits can therefore erase part of
the amortization gain. Adverse planning bands are 6.10–6.50 and 6.75–7.25 seconds,
respectively. These are explicit hypotheses, not measured tails or guarantees.
For an admitted dg1/xpu:2 arm only, a graph cone could remove about 0.15–0.25 s,
while replica guards/text contention can add 0–0.20 s. Relative to dg0 this gives
145 roughly 5.30–6.15 and 169 5.75–6.80; no candidate speed benefit is established.

No native peak, new-length quality, cross-card byte identity or speed claim is
closed by this CPU census. The first arm must retain three-chain identity,
measured geometry, per-chunk display-last-frame/cone bytes, all existing floors
and safety walks; any later replica arm additionally needs full-frame xpu:2 vs
uncached eager xpu:3 qualification on all nine chunks.
