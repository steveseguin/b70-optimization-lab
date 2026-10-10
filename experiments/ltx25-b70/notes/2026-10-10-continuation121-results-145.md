# Packet 121 at 145 frames: refined memory census for packet 122

**Keep 169 frames disabled in both proposed arms.** The 145-frame sampler census
was conservative, but the new measured envelope still does not leave the requested
0.5 GiB near-floor allowance **plus a 0.25 GiB safety band** on every card at 169.
The display replica has ample room on xpu:2. It does not remove the sampler-card
constraint or all the retained reservation pressure on xpu:3.

The coordinator's next requested arm remains 145 frames, dg1 cap 1.0, eager
full display on xpu:2. Its expected cadence is promising, but xpu:3 admission
is an open risk. This CPU task does not launch or authorize it, and does not
weaken a floor or safety inspection to make it fit.

## Evidence and measurement limits

[CPU analysis script](../data/resume-20261008/continuation122-evidence-analysis.py)
and [frozen analysis output](../data/resume-20261008/continuation122-evidence.json)
bind 778 source files/observed file snapshots by SHA256. The script uses only
Python's standard library and regular-file reads. The 145 census fixes stream
sequences **0–50**, and cadence uses **40 consecutive intervals, 10→11 through
49→50**. The 97/121 comparison fixes sequences 0–110 and 100 intervals, 10→11
through 109→110. It does not silently mix a growing live sample into a statistic.
Live client logs and manifests are hashed as the bytes observed, not claimed to
be immutable on disk. Regenerating the analysis later changes those snapshot
hashes even though the bounded receipt sample is unchanged.

Run identities:

- 145: `encoder-server-continuation-stream-121-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145`;
  actual display is **xpu:3**, as receipt `server_options` and freeze establish.
  The inherited `dxpu2` basename is not display placement authority.
- 121 replica: `encoder-server-continuation-stream-120-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121-dseager-display-ra0-ssfull-ddxpu2`.
- 121 dg0: packet 118b session archived with suffix `.completed-20261010T033817Z`.
- 97: packet 117 `dg1-adcone-bo1-pa1`, ending `f97`.

145 freeze verdict is
`356b25be584b705e92f7d427359ccd50399075029fc6c122c929f1233982f188`,
on parent packet manifest
`8f1d4e3b5b8ca79f79a43b9a6f0acec252e58fdde72b92ffb5ea0743f71444dd`.
Measured geometry matches: image `[145,256,256,3]`, stage-A latent
`[1,128,19,4,4]`, stage-B latent `[1,128,19,8,8]`, audio latent
`[1,8,151,16]`, waveform `[1,2,288480]`. All 51 sampled streaming decodes have
`anchor_decode.equal=true`. The saved freeze reports the coordinator's
qualification; this CPU analysis did not rerun model quality tests.

**Free-memory readings are phase-boundary samples. Allocator `peak` is a
cumulative device high-water mark, not a reset isolated kernel peak.** A/B
conditioning records have physical free bytes but no phase-local allocator
peak. Neither an isolated upsampler peak nor a cone-vs-display peak can be
reconstructed from these receipts. We report the limits rather than invent
those measurements. All memory tables below use GiB (2^30 bytes); the live
status's GB values use decimal bytes.

## Measured 145-frame per-card census

| Phase, minimum physical free GiB | xpu:0 | xpu:1 | xpu:2 | xpu:3 |
|---|---:|---:|---:|---:|
| Preparation snapshot, before sampler captures | 10.965061 | 10.574425 | 11.836716 | 14.852520 |
| Request before | 9.422718 | 9.828312 | 11.836678 | 10.849663 |
| Stage A before/after conditioning | 9.453979 | 9.847855 | 11.836689 | 14.664127 |
| Stage B before/after conditioning | **9.270382** | 9.847843 | **11.705818** | 10.859428 |
| Request after | 9.301632 | **9.828312** | 11.705826 | **10.849663** |
| Minimum over those sites | **9.270382** | **9.828312** | **11.705818** | **10.849663** |
| Margin above conservative 8 / 8 / 2 / 9 GiB floor | **1.270382** | **1.828312** | **9.705818** | **1.849663** |

The sampler cards require 8 GiB at request/conditioning; xpu:3 requires 9 GiB
before decode/conditioning and at request entry. Request-after has a 2 GiB
physical guard, but the near-floor inspector compares its snapshot with the
stricter card floors. The table conservatively uses the stricter floors at
all sites, including reservations that can survive until the next request.
The minimum snapshot margin in this broader sample is 1,364,062,208 bytes
(1.270382 GiB), not the 1.39 GB of the earlier interior-only status sample.

| Cumulative allocator measurement, GiB | xpu:0 | xpu:1 | xpu:2 | xpu:3 |
|---|---:|---:|---:|---:|
| Largest sampled allocated | 20.260300 | 20.498208 | 16.530899 | 14.176737 |
| Largest recorded allocated peak | **20.559114** | **20.763804** | **18.073120** | **16.657144** |
| Largest sampled reserved | 21.255859 | 21.326172 | 19.000000 | 19.751953 |

The **upsampler lives on xpu:0** and is followed by the lowest xpu:0 reading
at B preparation; A-to-B median timing for the native upsampler is 0.046 s.
It cannot be isolated from the sampler's captured routes and retained storage
by subtracting these samples. Stage A/B anchors remain single images, so their
native encoder input is not multiplied by the full chunk length.

On xpu:3 the minimum sampled **before-cone** free is **14.533268 GiB**,
a 5.533268 GiB margin over its 9 GiB floor. During B preparation, when the
previous full display overlaps, sampled free reaches **10.859428 GiB**;
request-before/after reaches **10.849663 GiB**. Thus display/encode/audio and
retained reservations account for a substantial difference from cone admission.
The aggregate preparation-to-minimum loss is **4.002857 GiB**. The recorded
allocated peak is 2.023314 GiB above the preparation allocated value, but its
lifetime includes multiple phases; it is not a measured cone transient.

xpu:2 is idle **for video display**, not empty: it retains text weights and
performs text work. Its physical free floor is 11.705818 GiB and the historical
text high-water is 18.073120 GiB allocated. A replica must coexist with that work.

Compared with the [packet 121 design](2026-10-10-continuation121-stream-design.md):

| 145 margin over floor, GiB | Earlier prediction | Measured | What changed |
|---|---:|---:|---|
| xpu:0 | 0.683–1.043 | 1.270 | 0.227–0.587 more room than predicted |
| xpu:1 | 1.613–1.765 | 1.828 | 0.063–0.215 more room |
| xpu:2, no replica | 9.706 | 9.706 | Matches within rounding |
| xpu:3, dg0 | 1.566–2.243 | 1.850 | Inside range: 0.284 above low end, 0.393 below high end |

The sampler reserve envelope grew much less than scaling the entire old loss
quadratically predicted. The xpu:3 envelope was not uniformly overestimated:
its measured value is within the old interval. The design's 3.2–3.5 s eager
display prediction was conservative by 0.48–0.78 s; measured median is 2.719 s.

## Cadence and fixed work per chunk

Periods are submit-to-next-submit. The sustained denominator drops the repeated
anchor frame: 97/121/145 produce **4 / 5 / 6 seconds of new video**, respectively.
The earlier 120 note's 1.008 s/s used the nominal 121/24 seconds, not the 5.0
seconds of new anchored video. Both definitions are shown so the comparison is
honest. The 118b value here is the explicitly bounded first 100 interior
intervals, not the full-session 5.263 s summary in CURRENT.

| Quantity, median seconds | 117, 97, dg1 | 118b, 121, dg0 | 120, 121, dg1 replica | 121, 145, dg0 |
|---|---:|---:|---:|---:|
| Period | 4.688 | 5.291 | 5.082 | **5.611** |
| Period/new anchored seconds | 1.172 | 1.058 | 1.016 | **0.935** |
| Period/nominal seconds | 1.160 | 1.050 | 1.008 | 0.929 |
| Pure sampler A | 1.685 | 1.786 | 1.777 | 1.905 |
| Pure sampler B | 1.201 | 1.387 | 1.325 | 1.677 |
| Cone on chain | 0.691 graph | 0.978 eager | 0.770 graph | 0.875 eager |
| Upsample + B preparation | 0.329 | 0.285 | 0.278 | 0.295 |
| Text + A preparation | 0.514 | 0.498 | 0.499 | 0.511 |
| Anchor ready → receipt staged | 0.112 | 0.095 | 0.096 | 0.101 |
| Full display, off-chain | 1.554 | 2.683 | 2.681 | 2.719 |
| Period − pure A − B − cone, computed per interval | 1.104 | 1.135 | 1.219 | 1.156 |

145: mean 5.752 s, p10 5.449, p90 6.236 (40 intervals). This agrees with the
coordinator's earlier 24-interval median 5.612 s. It does not establish a
fresh-server repeat. 120: mean 5.140, p10 4.807, p90 5.594 (100 intervals).
Do not add all snapshot durations to these buckets: they already occur inside
conditioning, receipt, and request preparation.

A descriptive least-squares fit through 97/121/145 gives sampler A
`1.23534 + 0.00459970 × frames` seconds and sampler B
`0.223061 + 0.00990570 × frames`. At 169 their extrapolated central values
are 2.013 and 1.897 s. The 121→145 pure A+B increase is 12.9% against 118b
(3.172→3.582 s) or 15.5% against 120 (3.102→3.582 s), for 19.8% more total
frames. These are measured comparisons of different sessions, not an isolated
kernel scaling law.

Cone time is **not monotonic**: 97 graph 0.691, 121 graph 0.770 / eager 0.978,
145 eager 0.875. The cone keeps a bounded last-frame dependency and tiled work;
changing chunk alignment, graph mode, allocator state and scheduling prevents
a causal three-point scaling fit. The descriptive mixed-arm cone fit predicts
1.032 s at 169, but planning uses a wider 0.85–1.10 s eager band. No forecast
is a measured point or a speed claim.

The full-period affine fit is `2.86907 + 0.0192382 × frames` seconds. Its
**2.87 s fitted zero-frame intercept is an extrapolated affine intercept**,
including the kernels' own intercepts, not a directly measured fixed CPU cost.
The useful non-sampler/non-cone residual is **about 1.10–1.22 s per chunk**
(median) or **1.25–1.29 s** (mean including periodic safety work). Fitting
those median residuals gives `0.99887 + 0.00109659 × frames`; this is the
roughly 1.1–1.3 s per chunk that longer chunks amortize. The mixed graph modes
and only three lengths do not support a unique decomposition of fixed cost.

## Refined 169 census and admission decision

Use the **measured 145 preparation-to-minimum physical-free loss** on each
sampler card and on dg0 xpu:3. For 169, scale that complete envelope between
`r=22/19` and `r²`. This includes captured routes, native workspaces and
retained reservations; it deliberately avoids multiplying all resident weights.
The ranges are engineering scenarios, not statistical confidence intervals or
proven peak bounds. They improve the old 169 xpu:0 conservative margin from
−0.095 to +0.693 GiB, but positive alone is insufficient.

For dg1/xpu:2, use the **actual 120 replica arm**, not the old no-replica 119
pressure. Its capture retains **3,430,940,672 bytes = 3.1953125 GiB**. `cap=1.0`
means a 1,000,000,000-byte post-capture admission threshold, not a hard 1 GB pool
bound: the first captured method crosses it. Scale this pool linearly with
latent frames, giving **3.794434 GiB at 145 and 4.393555 GiB at 169** (4.074 and
4.718 decimal GB). Scale the remaining physical loss from 121 linearly through
quadratically. Keep the measured retained-reference/audio envelope: moving the
full display does not prove all xpu:3 transient storage disappears.

A critical 120 detail: A/B snapshots have about **12.023 GiB** free on xpu:3
and before-cone minimum is **11.964550 GiB**, but recurring request-before and
request-after readings fall to **9.712589 GiB**, just **0.712589 GiB** over 9.
These are real retained reservations, including seq 58 and 86, not a hypothetical
simultaneous cone plus display peak. Using only the clean conditioning boundary
would miss them. The non-pool preparation-to-minimum loss is **about 1.945 GiB**.

| 169 arm, margin above unchanged floor, GiB | xpu:0 / 8 | xpu:1 / 8 | xpu:2 / 2 | xpu:3 / 9 |
|---|---:|---:|---:|---:|
| dg0, display xpu:3 | **0.693–1.003** | 1.574–1.711 | 9.706 | **0.486–1.218** |
| dg1 cap 1.0, eager display xpu:2 | **0.693–1.003** | 1.574–1.711 | 2.210 after proposed 6.5 GiB budget | **−2.218 to −1.215** |

The required screening margin is **0.75 GiB = 0.5 GiB near-floor allowance +
0.25 GiB explicit safety band**. dg0 misses it by 0.057 GiB on xpu:0 and
0.264 GiB on xpu:3 in the conservative scenario. Its xpu:3 conservative case
is even below the 0.5 GiB near-floor threshold. The replica arm also fails;
a display replica cannot repair xpu:0, and its graph/retained reservation
estimate crosses xpu:3's floor. **Neither arm enables 169 in packet 122.**

A future admission needs measured peak/reservation behavior that tightens these
bounds, or documented reductions of at least those dg0 deficits **plus evidence
that the retained reservation tails remain covered**. For the dg1 replica arm,
the current conservative shortfall to the 0.75 GiB target is about 2.97 GiB on
xpu:3. The coordinator's 145 graph-replica receipts can show whether the pool
and the non-pool tail actually grow this way; a new audited census can then
reopen 169. Do not turn the linear optimistic scenario into permission or
change floors, safety walks, host settings or precision.

## The coordinator's next 145 graph-replica arm

Replica weights are **834,267,746 bytes** (0.777 GiB). The saved 120
`display_replica.residency.last_decode` records show maximum observed
peak-or-reservation growth **3,202,351,104 bytes = 2.982422 GiB**; this value
also matches the client's manifest records. Scaling linearly/quadratically
with latent frames yields:

| Candidate | Display growth, GiB | Old 4 GiB adequate for upper scenario? | Planned budget | xpu:2 margin after budget and 2 GiB floor |
|---|---:|---|---:|---:|
| 145 | 3.542–4.206 | **No**, short by 0.206 | **5.640625 GiB inherited default** | **3.070 GiB** |
| 169, disabled | 4.101–5.639 | **No**, short by 1.639 | 6.5 GiB design scenario only | 2.210 GiB |

The xpu:2 calculation starts from the lowest 120 **before-decode** free reading,
11,500,101,632 bytes = 10.710304 GiB, which already includes the replica weights
and text coexistence. Do not subtract the weight copy a second time. It then
reserves the entire candidate budget plus the 2 GiB floor. There is room to
raise the allowance. At 145, a 5 GiB arithmetic scenario would exceed the upper growth estimate
by 0.794 GiB, but packet 122 retains the safer **5.640625 GiB minimum and default**.
The launch option permits only increases, up to **8 GiB**, and binds the selected
allowance into the plan/runtime identity. Before-copy, before-decode, after-decode
and measured-growth checks remain. An 8 GiB allowance leaves 0.710 GiB above
the xpu:2 floor in this conservative predecode census; that is below the 0.75 GiB
screening target, so it is not the recommended setting. Never treat a larger
budget as a lower free-memory floor.

| 145 dg1/xpu:2 forecast margin, GiB | xpu:0 | xpu:1 | xpu:2 | xpu:3 |
|---|---:|---:|---:|---:|
| Measured sampler envelope + scaled 120 replica/pool envelope | 1.270 | 1.828 | 3.070 after default budget | **−0.684 to −0.251** |

This pessimistic xpu:3 estimate does not prove a runtime failure; reservations
can be reused, and the whole non-pool loss is not a single live tensor set.
It **does** mean the available CPU evidence cannot certify that the next arm
clears the 9 GiB boundary. Report any native refusal as a useful result and
retain all guards. No automatic fallback/restart is part of this work.

## Recommended comparison order, text only

1. **145, dg1 cap 1.0, eager display xpu:2**, full snapshots, read-ahead off,
   inherited 5.640625 GiB replica allowance. This is the coordinator's already
   requested next comparison. Conditional on memory admission and exact
   same-length qualification: predicted **5.35–5.90 s per 6.0 s of new video =
   0.892–0.983 s/s** (central about 5.45 s, 0.908 s/s). A 0.1–0.25 s cone
   saving is plausible; extra safety walks, FIFO or text contention can push
   it to **5.90–6.40 s = 0.983–1.067 s/s**, or the arm may refuse on memory.
2. **145, dg0, display xpu:3** is the established comparison: measured 5.611 s,
   0.935 s/s in this receipt slice; a repeat planning band is **5.45–6.10 s =
   0.908–1.017 s/s**. This is reference text, not an instruction to stop or
   replace the coordinator's current service.
3. **Do not launch 169 with packet 122.** For future design only, dg0 is
   predicted **5.95–6.55 s per 7.0 s = 0.850–0.936 s/s**; dg1/xpu:2 is
   **5.70–6.40 s = 0.814–0.914 s/s** if its memory problems are solved. These
   forecasts are not enabled configurations and not measured performance.

Open evidence: isolated per-phase native peaks, 145 graph-replica capture and
reservation tails, its exact full-frame cross-card equality, its full-model
same-length qualification, sustained cadence and a fresh-run repeat; all
169 measurements; owner visual/listening judgement of seams and audio.
No device, server, launch, check-only, systemd, port, process signal, host setting,
existing run write or live-client write was used for this analysis.

Packet 122 CPU implementation and seal are recorded separately in its
[contract](../recovery/20261010-continuation122-stream/CONTRACT.md),
[launch reference](../recovery/20261010-continuation122-stream/LAUNCH.md), and
[build receipt](../data/resume-20261008/continuation122-build.json).

While this CPU packet was being built, the coordinator added a 04:34 UTC entry
to `CURRENT.md`: a preview-file read race stopped the 121 client at chunk 154;
the coordinator resumed the client. This occurred after the frozen 0–50 census
window. Packet 122 retains the inherited preview publication/read behavior;
that race is **not fixed by this memory-census packet** and remains a separate
follow-up. No live operation was performed by this task.

## Packet 122 seal and CPU validation

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-122`.
Manifest SHA256: `8b576c863ec5896fe356e5a264728ddafe368ef2fe90608c9b5bc164687cb7fa`.
Plan SHA256: `0ef91a395112bd7d1ffecbbc2d74bf5ccc89267751447be9b21a4b4ec107c060`.
All **2,005 bound files** verify recursively. Packet and authored sources contain
zero `__pycache__` directories and zero `.pyc` files. The 176 parent numerical
identities and all 3,168 normalized qualification graphs remain identical.

**489 unique recovery checks validated, no skips.** Full discovery ran 482,
with one copied fixture still expecting the successor to add numerical IDs.
122 intentionally retains all 176; the corrected complete 16-test assembly
module passed. The new reserve module grew from 21 to 28 cases and passed in
full, including the real production status handler, actual client option parser,
and a real Runtime driven by CPU fakes through nine qualification and two live
chunks at 145/dg1/cap1/xpu:2 with an explicit 6 GiB reserve. Reruns are not added
to the unique count. **783/783 client checks** passed: 571 inherited and 212 new
checks (138 unit, 74 fake HTTP), with all new checks repeated against the final
seal. **10/10 mocked preflight tests** and both wrappers' `bash -n` checks passed.
No launcher or real preflight was executed.

Two never-launched development seals were rejected by CPU review/testing: the
receipt validator initially rejected the optional reserve field, then the
production status route omitted its top-level export to the client. Both are
fixed and regression-tested; their build receipts and local prepared artifacts
are preserved separately. Earlier development failures from copied plan pins
and fixture assertions remain in logs and are not final passes. The
[build receipt](../data/resume-20261008/continuation122-build.json) binds the
final inputs, tests, earlier rejected seals and their limitations.
