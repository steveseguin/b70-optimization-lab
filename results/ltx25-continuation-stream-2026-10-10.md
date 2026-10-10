# LTX 2.5 continuation-stream campaign ledger — 2026-10-09/10

**Production configuration: packet 129, 145 frames, decoder graph off, legacy auxiliaries, serial display on xpu:3, idle maintenance, GC60, immutable digest cache and background storage scan.** Its completed 609-chunk session measured **5.554 s median / 5.947 s mean / 6.239 s p90**, or **0.926 seconds of work per second of new video** by the median. “Production” names the coordinator-selected campaign configuration, not a claim that a service is now running.

**Best measured 145-frame median: packet 127, 5.467 s (0.911 s/s).** Packet 128 measured 5.493 s with idle/GC10 and 5.528 s with idle/GC60: the retained best range is **about 5.47–5.53 s, or 0.91–0.92 s/s**. These single-session observations do not establish a repeated fresh-server speed record. Packet 129 adds reliability; its longer session must not inherit packet 127's faster number.

This ledger covers 24 completed/refused launches from packets 117 through 129, including the October 9 baselines, plus the pending packet-131 launch. The final evidence capture found 131's client header and first qualification request at 11:32:09.449 UTC, but no qualification verdict or streamed chunk; its result remains pending. Prepared-only packets are recorded below. Evidence was read only, with CPU work at nice19 and OMP_NUM_THREADS=2. No device, service, endpoint, unit, live-client or existing-run write occurred. No /tmp scratch was created.

The [chronological campaign note](../notes/2026-10-10-ltx-continuation-campaign.md) explains the changes and corrected diagnoses. The [machine-readable ledger](../data/ltx25-continuation-stream-2026-10-10.json) preserves source file hashes, exact run directories, qualification summaries, submitted timestamps, intervals, incidents and digest-comparison counts. The [analyzer](../scripts/analyze-ltx-continuation-ledger.py) reproduces it without importing model/runtime code.

## Measurement and evidence boundary

- Period is the difference between consecutive `submitted stream…-sNNNNNNNN` timestamps in `client.log`, for destination `stream_seq >= 10`. Thus 9→10 is included. Time resolution is one millisecond. Even/odd labels refer to the **destination** sequence; source-parity analyses in the lane notes reverse them.
- Each client invocation is a separate timing segment. The 121 and 127 resume intervals are listed as incidents, not bridged into steady-state periods. All other observed intervals remain, including pauses above 12 seconds. No selected slow prompt or maintenance interval is removed. Including the resume gaps gives 121 first-session mean 6.069 s (410 intervals) and 127 mean 6.536 s (86 intervals); the primary means are 5.841 and 5.585 respectively.
- Median and arithmetic mean use the full saved session after that cutoff. P90 uses nearest rank `ceil(0.9*n)` without interpolation. This deliberately differs from interim/fixed-window notes and source-parity interior windows. Three-decimal display rounds halves upward.
- Work/video is median period divided by **(frames−1)/24**: 4, 5, 6 or 7 new seconds at 97, 121, 145 or 169 frames. The first unanchored chunk is outside the timing window. Earlier notes sometimes divided by frames/24; those nominal ratios are not copied here. Mean-based work/video for 129 is 0.991 s/s.
- “Chunks” counts committed client manifest rows, including rows recovered after a client resume; `n` counts measured intervals. Saved manifests, rather than interim CURRENT counts, give 173 for the earlier 117/121 session, 135 for 120, and 609 for 129.
- All 22 completed qualifications pass exact three-chain replay at c0/c1/c2. The 97-frame qualification also compares against packet 114. The 145-frame qualifications from 123b onward compare all three chunks and seven tensor/file fields against packet 121. The first 121- and 145-frame baselines and the 169-frame run have no earlier same-geometry reference. A qualification pass is not a fresh-server repeat.
- `N/N ← reference` below means a CPU comparison of saved `images_sha256`, `last_frame_sha256`, `anchor_sha256` and `preview_sha256`: all four match on every shared stream sequence, with frame count, scene and seed checked. It does not claim a new media/tensor read. All streamed manifest rows report `cone_equal=true`. These are the repeated ten-scene continuation workload, not a cold varied-model benchmark or an external leaderboard submission.

## Launched configurations

All runs use four B70s, 256×256 video, 24 fps, frame anchors, two-way20–28 sampler placement, cone anchor decode, stage-B encode overlap and prep-ahead. `dg` means decoder graph. Display is xpu:3/serial with `sampler-a` scheduling unless listed as `eager`; 124 and the 127/169 attempt also use early audio. Legacy auxiliaries keep the upsampler on xpu:0 and audio VAE/vocoder on xpu:3; `xpu2` moves those auxiliaries.

Options are **GC seconds / maintenance / digest cache / storage scan**. `parent` retains the inherited maintenance schedule; `request` means synchronous request-path scanning/accounting. Packets before these knobs existed use their parent defaults, not a claim that the option was accepted by those launchers. All snapshot schedules are `full`; snapshot mode is `walk` for 117 and `fingerprint` thereafter. Decoder graph cap is absent for 117 and 1,000,000,000 bytes for 118b/119/120 dg1 (a post-capture cap, not a first-capture bound). Only 119 has anchor read-ahead enabled. Run IDs resolve to exact saved directory names in the next table. Work directories have prefix `/home/steve/ltx-stream/`.

| Run / packet | Frames / dg | Display device / worker | Aux | GC / maintenance / digest / scan | Work directory | Verdict ID | Chunks / n | Period median / mean / p90 (s) | Even / odd medians (s) | Work/video (s/s) | Byte identity vs saved reference | Stop / incident and cause | Outcome |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- | ---: | --- | --- | --- |
| R01 / 117 | 97 / 1 | xpu:3/serial | legacy | 10 / parent / 0 / request | `s117-stream01` | `76a9153848bd` | 134 / 124 | 4.762 / 4.846 / 5.144 | 4.646 / 5.040 | 1.191 | 72/72 images+anchor ← 116b (historical note); 3/3 qualification ← 114 | Controlled stop for next arm; no client incident. | win vs 116b |
| R02 / 117 | 121 / 1 | xpu:3/serial | legacy | 10 / parent / 0 / request | `s117-stream01` | — | 0 / 0 | — | — | — | Qualification incomplete | Qualification: xpu:3 floor, 76 MB short; no GPU fault. | refused |
| R03 / 117 | 121 / 0 | xpu:3/serial | legacy | 10 / parent / 0 / request | `s117-stream01` | `cff20f16ae37` | 173 / 163 | 5.205 / 5.386 / 5.863 | 5.124 / 5.526 | 1.041 | No predecessor comparison; own replay exact | Controlled stop for next arm; no client incident. | win per new second vs 97 |
| R04 / 117 | 121 / 0 | xpu:3/serial | legacy | 10 / parent / 0 / request | `s117-live01` | `508f2f2bac6a` | 63 / 53 | 5.303 / 5.507 / 6.018 | 5.221 / 5.814 | 1.061 | No predecessor comparison; own replay exact | Controlled stop for next arm; no client incident. | neutral repeat |
| R05 / 118b | 121 / 0 | xpu:3/serial | legacy | 10 / parent / 0 / request | `s118b-live01` | `6824dd4a6fae` | 101 / 91 | 5.195 / 5.356 / 5.850 | 5.070 / 5.503 | 1.039 | 63/63 ← s117-live01 | Controlled stop for next arm; no client incident. | win observed; small |
| R06 / 118b | 121 / 1 | xpu:3/serial | legacy | 10 / parent / 0 / request | `s118b-dg1-live01` | `493c3b66a3ec` | 37 / 27 | 5.559 / 5.541 / 5.776 | 5.561 / 5.367 | 1.112 | 37/37 ← s118b-live01 | Controlled stop for next arm; no client incident. | loss vs dg0 |
| R07 / 118b | 121 / 0 | xpu:3/serial | legacy | 10 / parent / 0 / request | `s118b-live02` | `08301c03a083` | 271 / 261 | 5.279 / 5.416 / 5.888 | 5.125 / 5.667 | 1.056 | 101/101 ← s118b-live01 | Controlled stop for next arm; no client incident. | neutral repeat |
| R08 / 119 | 121 / 1 | xpu:3/serial; eager | legacy | 10 / parent / 0 / request | `s119-live01` | `9dac6eb450ba` | 61 / 51 | 5.435 / 5.402 / 5.552 | 5.441 / 5.241 | 1.087 | 61/61 ← s118b-live02 | Controlled stop for next arm; no client incident. | loss vs dg0 |
| R09 / 118b | 121 / 0 | xpu:3/serial | legacy | 10 / parent / 0 / request | `s118b-live03` | `592b7c7ebabd` | 167 / 157 | 5.263 / 5.401 / 5.868 | 5.127 / 5.629 | 1.053 | 167/167 ← s118b-live02 | Controlled stop for next arm; no client incident. | neutral repeat |
| R10 / 120 | 121 / 1 | xpu:2/serial; eager | legacy | 10 / parent / 0 / request | `s120-live01` | `0d3305d1a160` | 135 / 125 | 5.092 / 5.132 / 5.591 | 4.907 / 5.245 | 1.018 | 135/135 ← s118b-live03 | Controlled stop for next arm; no client incident. | win vs dg0 |
| R11 / 121 | 145 / 0 | xpu:3/serial | legacy | 10 / parent / 0 / request | `s121-live01` | `356b25be584b` | 420 / 409 | 5.714 / 5.841 / 6.305 | 5.527 / 5.945 | 0.952 | No predecessor comparison; own replay exact | Preview HTTP500 at 154; client resumed (99.360 s gap). Storage HTTP409 after 420; whole-filesystem accounting. | win per new second |
| R12 / 121 | 145 / 0 | xpu:3/serial | legacy | 10 / parent / 0 / request | `s121-live02` | `9a57f69a751f` | 316 / 306 | 5.760 / 5.905 / 6.300 | 5.548 / 5.908 | 0.960 | 316/316 ← s121-live01 | Controlled stop for next arm; no client incident. | neutral repeat |
| R13 / 123b | 145 / 0 | xpu:3/serial | xpu2 | 10 / parent / 0 / request | `s123b-live01` | `d410928322ba` | 41 / 31 | 5.733 / 5.929 / 6.408 | 5.639 / 6.087 | 0.955 | 41/41 ← s121-live02 | Client preflight exit8: wrong plan pin; fixed before qualification. Controlled stop. | neutral; memory win |
| R14 / 123b | 169 / 0 | xpu:3/serial | xpu2 | 10 / parent / 0 / request | `s123b-f169-live01` | `4eeb3b603c94` | 49 / 39 | 6.824 / 6.981 / 7.433 | 6.713 / 7.187 | 0.975 | No predecessor comparison; own replay exact | Controlled stop for next arm; no client incident. | loss vs 145 |
| R15 / 123b | 145 / 0 | xpu:3/serial | xpu2 | 10 / parent / 0 / request | `s123b-live02` | `fe5fad177140` | 213 / 203 | 5.894 / 6.011 / 6.499 | 5.707 / 6.162 | 0.982 | 41/41 ← s123b-live01 | Controlled stop for next arm; no client incident. | loss vs 121; cause mixed |
| R16 / 123b | 145 / 0 | xpu:3/serial | legacy | 10 / parent / 0 / request | `s123b-legacy-live01` | `b6bcdae18297` | 61 / 51 | 5.770 / 5.973 / 6.445 | 5.697 / 6.118 | 0.962 | 61/61 ← s121-live02 | Controlled stop for next arm; no client incident. | loss vs early 121; bookkeeping |
| R17 / 124 | 145 / 0 | xpu:2/parallel; eager | legacy | 10 / parent / 0 / request | `s124-live01` | `24e7fd6c6dbb` | 45 / 35 | 5.746 / 5.908 / 6.440 | 5.574 / 6.057 | 0.958 | 45/45 ← s123b-legacy-live01 | Controlled stop for next arm; no client incident. | neutral vs 123b legacy |
| R18 / 125 | 145 / 0 | xpu:3/serial | legacy | 60 / parent / 0 / request | `s125-live01` | `7c1e8a6ef3b2` | 217 / 207 | 5.785 / 5.902 / 6.237 | 5.740 / 6.051 | 0.964 | 61/61 ← s123b-legacy-live01 | Controlled stop for next arm; no client incident. | neutral vs 123b legacy |
| R19 / 126 | 145 / 0 | xpu:3/serial | legacy | 10 / parent / 0 / background | `s126-live01` | `a4b739676c5a` | 251 / 241 | 5.759 / 5.876 / 6.351 | 5.559 / 5.924 | 0.960 | 217/217 ← s125-live01 | Controlled stop for next arm; no client incident. | win in matched budget; modest |
| R20 / 127 | 169 / 0 | xpu:2/parallel; eager | legacy | 10 / parent / 0 / background | `s127-f169-live01` | — | 0 / 0 | — | — | — | Qualification incomplete | Qualification: xpu:2 replica memory refusal; no GPU fault. Earlier GC60 scope rehearsal refused. | refused |
| R21 / 127 **best** | 145 / 0 | xpu:3/serial | legacy | 60 / parent / 1 / background | `s127-live01` | `cbd91ba8a8cc` | 96 / 85 | 5.467 / 5.585 / 6.043 | 5.440 / 5.700 | 0.911 | 96/96 ← s126-live01 | Decode HTTP500 at 80; client resumed (87.372 s gap); controlled stop. | win; best median |
| R22 / 128 | 145 / 0 | xpu:3/serial | legacy | 10 / idle / 1 / background | `s128-live01` | `86134e704d4f` | 70 / 60 | 5.493 / 5.639 / 5.961 | 5.455 / 5.792 | 0.915 | 70/70 ← s127-live01 | Controlled stop for next arm; no client incident. | win vs 126; near 127 |
| R23 / 128 | 145 / 0 | xpu:3/serial | legacy | 60 / idle / 1 / background | `s128-gc60-live01` | `0d1d0d811ce2` | 71 / 61 | 5.528 / 5.643 / 6.009 | 5.500 / 5.841 | 0.921 | 70/70 ← s128-live01 | Controlled stop for next arm; no client incident. | neutral vs 127/128 |
| R24 / 129 **production** | 145 / 0 | xpu:3/serial | legacy | 60 / idle / 1 / background | `s129-live01` | `da3f9f5eb39a` | 609 / 599 | 5.554 / 5.947 / 6.239 | 5.503 / 5.840 | 0.926 | 71/71 ← s128-gc60-live01 | Controlled stop, 609 chunks; no client stop/error. | win in reliability; neutral speed |
| R25 / 131 | 145 / 1 | xpu:2/serial; eager | legacy | 60 / idle / 1 / background; cone memory `replica-release` | `s131-live01` | pending | 0 / 0 | — | — | — | Not yet qualified | First qualification request submitted; no stop in captured prefix. | pending; no win/loss assigned |

## Run identities

Each exact directory below is relative to `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/`. It contains `stream-qualification-verdict.json` for completed gates; the verdict ID above is that file's SHA256 prefix. The JSON retains the full path and full SHA256. Client log headers contain the original name before archive suffixes. The two refused rows instead retain failure/halt evidence; neither has a pass verdict.

| Run | Saved run directory |
| --- | --- |
| R01 | `encoder-server-continuation-stream-117-frame-dg1-adcone-bo1-pa1-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97` |
| R02 | `encoder-server-continuation-stream-117-frame-dg1-adcone-bo1-pa1-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121` |
| R03 | `encoder-server-continuation-stream-117-frame-dg0-adcone-bo1-pa1-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121.completed-20261009T0225Z` |
| R04 | `encoder-server-continuation-stream-117-frame-dg0-adcone-bo1-pa1-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121` |
| R05 | `encoder-server-continuation-stream-118b-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121.completed-20261010T0156Z` |
| R06 | `encoder-server-continuation-stream-118b-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121` |
| R07 | `encoder-server-continuation-stream-118b-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121.completed-20261010T0250Z` |
| R08 | `encoder-server-continuation-stream-119-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121-dseager-display-ra1-ssfull` |
| R09 | `encoder-server-continuation-stream-118b-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121.completed-20261010T033817Z` |
| R10 | `encoder-server-continuation-stream-120-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121-dseager-display-ra0-ssfull-ddxpu2` |
| R11 | `encoder-server-continuation-stream-121-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145.completed-20261010T050411Z` |
| R12 | `encoder-server-continuation-stream-121-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145.completed-20261010T054956Z` |
| R13 | `encoder-server-continuation-stream-123b-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-auxxpu2.completed-20261010T063121Z` |
| R14 | `encoder-server-continuation-stream-123b-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f169-auxxpu2` |
| R15 | `encoder-server-continuation-stream-123b-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-auxxpu2.completed-20261010T070202Z` |
| R16 | `encoder-server-continuation-stream-123b-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145.completed-20261010T072208Z` |
| R17 | `encoder-server-continuation-stream-124-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-ddxpu2-dwparallel` |
| R18 | `encoder-server-continuation-stream-125-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-gc60` |
| R19 | `encoder-server-continuation-stream-126-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-ssbackground` |
| R20 | `encoder-server-continuation-stream-127-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f169-dseager-display-ra0-ssfull-ddxpu2-dwparallel-ssbackground` |
| R21 | `encoder-server-continuation-stream-127-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-gc60-ssbackground-sdc1` |
| R22 | `encoder-server-continuation-stream-128-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-ssbackground-sdc1-mi` |
| R23 | `encoder-server-continuation-stream-128-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-gc60-ssbackground-sdc1-mi` |
| R24 | `encoder-server-continuation-stream-129-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-gc60-ssbackground-sdc1-mi` |
| R25 | `encoder-server-continuation-stream-131-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-ddxpu2-gc60-ssbackground-sdc1-mi-cmreplica-release` |

## Refusals, reliability fixes and unlaunched work

The 117/121 dg1 qualification refused with xpu:3 free 9,587,769,344 B below the unchanged 9,663,676,416 B floor. The 127/169 replica attempt refused with xpu:2 free 8,465,399,808 B below 6.5 GiB transient reserve plus the 2 GiB floor. Neither was a GPU fault or an exactness failure. Including the existing 0.75 GiB screening margin, the latter needs **1.366 GiB** reclaimed, not merely the 0.616 GiB in the immediate floor comparison. The first GC60 rehearsal was rejected by launch scope and did not launch another server. See [169 inventory](../experiments/ltx25-b70/notes/2026-10-10-xpu2-residency-169.md).

The 121 preview and 127 decode-record incidents were writer/reader evidence races. The guard stopped the client while the server chain remained intact. Packet 123 made preview publication atomic; packet 129 extends temp-write/fsync/rename to every route-read evidence file. Packet 121's storage stop charged all filesystem writers to the run's 3 GiB allowance; 123b counts only run-owned writes, and the measured launches use a 16 GiB allowance. The separate 50 GiB filesystem reserve remains. The 123b client initially pinned the outer plan-file hash instead of its inner plan hash, then qualified after correction. These are recorded incidents, not grounds to discard the failed arms.

| Packet | Disposition at cutoff | Evidence |
| --- | --- | --- |
| 118 | CPU review blocked; withdrawn, never launched. Snapshot memory-verdict/schedule checks and pool-cap retention corrected in 118b. | [review](../experiments/ltx25-b70/notes/2026-10-09-continuation118-review.md), [rebuild](../experiments/ltx25-b70/notes/2026-10-09-continuation118b-rebuild.md) |
| 122 | Census/reserve refinement only; no native launch. 145 dg1 and 169 stayed behind memory admission. | [145 census](../experiments/ltx25-b70/notes/2026-10-10-continuation121-results-145.md) |
| 123 | CPU prepared; never launched separately. Preview/residency work inherited by 123b. | [design](../experiments/ltx25-b70/notes/2026-10-10-continuation123-stream-design.md) |
| 130 | CPU sealed; 169 guarded allocator release unmeasured, no launch. | [design](../experiments/ltx25-b70/notes/2026-10-10-continuation130-stream-design.md) |
| 131 | CPU sealed; launch observed (R25), native result pending. 145 dg1 cone graph, serial eager display replica xpu:2, guarded release, idle/GC60/digest/background, legacy auxiliaries. No speed assigned. | [design](../experiments/ltx25-b70/notes/2026-10-10-continuation131-stream-design.md), [snapshot decision](../experiments/ltx25-b70/notes/2026-10-10-continuation131-snapshot-schedule.md) |

Build receipts pin the packet identities and CPU checks, not native performance:
[117](../experiments/ltx25-b70/data/resume-20261008/continuation117-build.json) [118](../experiments/ltx25-b70/data/resume-20261008/continuation118-build.json) [118b](../experiments/ltx25-b70/data/resume-20261008/continuation118b-build.json) [119](../experiments/ltx25-b70/data/resume-20261008/continuation119-build.json) [120](../experiments/ltx25-b70/data/resume-20261008/continuation120-build.json) [121](../experiments/ltx25-b70/data/resume-20261008/continuation121-build.json) [122](../experiments/ltx25-b70/data/resume-20261008/continuation122-build.json) [123](../experiments/ltx25-b70/data/resume-20261008/continuation123-build.json) [123b](../experiments/ltx25-b70/data/resume-20261008/continuation123b-build.json) [124](../experiments/ltx25-b70/data/resume-20261008/continuation124-build.json) [125](../experiments/ltx25-b70/data/resume-20261008/continuation125-build.json) [126](../experiments/ltx25-b70/data/resume-20261008/continuation126-build.json) [127](../experiments/ltx25-b70/data/resume-20261008/continuation127-build.json) [128](../experiments/ltx25-b70/data/resume-20261008/continuation128-build.json) [129](../experiments/ltx25-b70/data/resume-20261008/continuation129-build.json) [130](../experiments/ltx25-b70/data/resume-20261008/continuation130-build.json) [131](../experiments/ltx25-b70/data/resume-20261008/continuation131-build.json) .

The campaign note preserves the four corrected readings: dg1's apparent graph-contention story versus the later near-floor dual-walk evidence; auxiliary-placement cost mixed with 123b bookkeeping; GC plus allocator cleanup rather than interval alone; and optimistic 169 xpu:2 census margins. Open items remain 169 memory, 131's native 145 cone-graph result, the owner's snapshot-schedule decision, Flash-Next probes awaiting the owner, and the storage cleanup proposal awaiting the owner. No such action was taken here.

`results/scoreboard.md` contained no LTX row at this audit and is unchanged. This is a durable campaign ledger, not a new public deployment package or promoted benchmark.

## Recompute without changing evidence

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B scripts/analyze-ltx-continuation-ledger.py
```

The command writes JSON to stdout only. The checked-in snapshot covers the saved logs through packet 129's clean stop at 2026-10-10 11:26:21.736 UTC, packet 131's first qualification request at 11:32:09.449 UTC, and CURRENT through the 11:35 UTC entry. The JSON embeds 131's captured client-log prefix and marks that source as able to grow. If later results appear, compare source hashes and record a new snapshot rather than silently treating them as this cutoff.
