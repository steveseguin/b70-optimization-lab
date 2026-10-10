# LTX 2.5 continuation-stream campaign ledger — 2026-10-09/10

**Production configuration and best clean completed line: packet 135, 145 frames, cone decoder graph on, split36 text placement, legacy auxiliaries, serial eager display on xpu:3, idle maintenance, GC60, immutable digest cache and background storage scan.** Its 121-chunk session measured **5.248 s median / 5.727 s mean / 5.919 s p90**, or **0.875 seconds of work per second of new video** by the median. “Production” names the coordinator-selected campaign configuration, not a claim that this audit checked a running service. The GC10 A/B is **in progress**, with qualification through Q04 submission in the captured log and no verdict or streamed chunk.

The halted first 133b session retains a lower observed median, **5.225 s (0.871 s/s)**, but stopped on the storage guard after 73 committed chunks. It is not a clean completed production result. The clean 133b repeat measured 5.390 s. Keep these windows separate from CURRENT's early 5.213 s observation and from 135; the storage repair alone has not been isolated as a speed improvement. These observations do not establish a repeated fresh-server speed record.

This extends the original packets 117–131 ledger through CURRENT's **2026-10-10 16:00 UTC** entry: 131/132 refusals, the unlaunched 133 rehearsal failure, two 133b sessions, sealed/unlaunched 134, completed 135 GC60 and the in-progress GC10 arm. The earlier 129 fallback sessions are chronology context, not new rows in this requested extension. Evidence was read only, with CPU work at nice19 and OMP_NUM_THREADS=2. No device, service, endpoint, unit, live-client or existing-run write occurred. No /tmp scratch was created.

The [chronological campaign note](../notes/2026-10-10-ltx-continuation-campaign.md) explains the changes and corrected diagnoses. The original [machine-readable snapshot](../data/ltx25-continuation-stream-2026-10-10.json) remains frozen at the first ledger's 11:35 UTC boundary; it does **not** contain this extension. The [original analyzer](../scripts/analyze-ltx-continuation-ledger.py) and the supplemental read-only calculation below document the same timing method. New source hashes, run identities and evidence links are recorded here without rewriting any evidence packet.

## Measurement and evidence boundary

- Period is the difference between consecutive `submitted stream…-sNNNNNNNN` timestamps in `client.log`, for destination `stream_seq >= 10`. Thus 9→10 is included. Time resolution is one millisecond. Even/odd labels refer to the **destination** sequence; source-parity analyses in the lane notes reverse them.
- Each client invocation is a separate timing segment. The 121 and 127 resume intervals are listed as incidents, not bridged into steady-state periods. All other observed intervals remain, including pauses above 12 seconds. No selected slow prompt or maintenance interval is removed. Including the resume gaps gives 121 first-session mean 6.069 s (410 intervals) and 127 mean 6.536 s (86 intervals); the primary means are 5.841 and 5.585 respectively.
- Median and arithmetic mean use the full saved session after that cutoff. P90 uses nearest rank `ceil(0.9*n)` without interpolation. This deliberately differs from interim/fixed-window notes and source-parity interior windows. Three-decimal display rounds halves upward.
- Work/video is median period divided by **(frames−1)/24**: 4, 5, 6 or 7 new seconds at 97, 121, 145 or 169 frames. The first unanchored chunk is outside the timing window. Earlier notes sometimes divided by frames/24; those nominal ratios are not copied here. Mean-based work/video for 129 is 0.991 s/s.
- “Chunks” counts committed client manifest rows, including rows recovered after a client resume; `n` counts measured intervals. Saved manifests, rather than interim CURRENT counts, give 173 for the earlier 117/121 session, 135 for 120, and 609 for 129. The second 133b session has **232 chunks / 222 intervals**; the reported 222 is n, not a chunk count. First-session 133b has 73 committed chunks but 64 intervals, because its final submitted request (sequence 73) later failed; the 72→73 submit interval remains under this ledger’s unchanged timing rule.
- The original 22 completed qualifications pass exact three-chain replay at c0/c1/c2. The 97-frame qualification also compares against packet 114. The 145-frame qualifications from 123b onward compare all three chunks and seven tensor/file fields against packet 121. The first 121- and 145-frame baselines and the 169-frame run have no earlier same-geometry reference. The three added completed qualifications (133b twice and 135 GC60) also pass c0/c1/c2 exact replay and all seven packet-121 reference fields. A qualification pass is not a fresh-server repeat.
- `N/N ← reference` below means a CPU comparison of saved `images_sha256`, `last_frame_sha256`, `anchor_sha256` and `preview_sha256`: all four match on every shared stream sequence, with frame count, scene and seed checked. It does not claim a new media/tensor read. All streamed manifest rows report `cone_equal=true`. These are the repeated ten-scene continuation workload, not a cold varied-model benchmark or an external leaderboard submission.

## Configurations and dispositions

All runs use four B70s, 256×256 video, 24 fps, frame anchors, two-way20–28 sampler placement, cone anchor decode, stage-B encode overlap and prep-ahead. `dg` means decoder graph. Display is xpu:3/serial with `sampler-a` scheduling unless listed as `eager`; 124 and the 127/169 attempt also use early audio. Legacy auxiliaries keep the upsampler on xpu:0 and audio VAE/vocoder on xpu:3; `xpu2` moves those auxiliaries.

Options are **GC seconds / maintenance / digest cache / storage scan**. `parent` retains the inherited maintenance schedule; `request` means synchronous request-path scanning/accounting. Packets before these knobs existed use their parent defaults, not a claim that the option was accepted by those launchers. All snapshot schedules are `full`; snapshot mode is `walk` for 117 and `fingerprint` thereafter. Decoder graph cap is absent for 117 and 1,000,000,000 bytes for 118b/119/120 dg1 (a post-capture cap, not a first-capture bound). Only 119 has anchor read-ahead enabled. In 133/133b/135, `split36` means text layers 0–35 on xpu:2 and 36–47 on xpu:3; layers **24–35** moved off xpu:3. Actual display placement comes from launch options, not the inherited `dxpu2` run-name token. The 133 and 134 rows are planned configurations, never native launches. Run IDs resolve to exact saved directory names in the next table. Work directories have prefix `/home/steve/ltx-stream/`.

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
| R21 / 127 (former best) | 145 / 0 | xpu:3/serial | legacy | 60 / parent / 1 / background | `s127-live01` | `cbd91ba8a8cc` | 96 / 85 | 5.467 / 5.585 / 6.043 | 5.440 / 5.700 | 0.911 | 96/96 ← s126-live01 | Decode HTTP500 at 80; client resumed (87.372 s gap); controlled stop. | win; former best median |
| R22 / 128 | 145 / 0 | xpu:3/serial | legacy | 10 / idle / 1 / background | `s128-live01` | `86134e704d4f` | 70 / 60 | 5.493 / 5.639 / 5.961 | 5.455 / 5.792 | 0.915 | 70/70 ← s127-live01 | Controlled stop for next arm; no client incident. | win vs 126; near 127 |
| R23 / 128 | 145 / 0 | xpu:3/serial | legacy | 60 / idle / 1 / background | `s128-gc60-live01` | `0d1d0d811ce2` | 71 / 61 | 5.528 / 5.643 / 6.009 | 5.500 / 5.841 | 0.921 | 70/70 ← s128-live01 | Controlled stop for next arm; no client incident. | neutral vs 127/128 |
| R24 / 129 (former production) | 145 / 0 | xpu:3/serial | legacy | 60 / idle / 1 / background | `s129-live01` | `da3f9f5eb39a` | 609 / 599 | 5.554 / 5.947 / 6.239 | 5.503 / 5.840 | 0.926 | 71/71 ← s128-gc60-live01 | Controlled stop, 609 chunks; no client stop/error. | win in reliability; neutral speed |
| R25 / 131 | 145 / 1 | xpu:2/serial; eager | legacy | 60 / idle / 1 / background; cone memory `replica-release` | `s131-live01` | — | 0 / 0 | — | — | — | Qualification incomplete | Q06 first cone capture refused: xpu:3 short 12,451,840 B; release recovered 0 B there. Exit 2; decode/session latches, no GPU fault. | refused |
| R26 / 132 | 145 / 1 | xpu:2/serial; eager | legacy; audio xpu:2 | 60 / idle / 1 / background; `replica-release` | `s132-live01` | — | 0 / 0 | — | — | — | Seven qualification decode pairs; no completed verdict | Capture admitted; qrepeat-c1 conditioning-B-before: xpu:3 9,103,118,336 B < 9,663,676,416 B floor. Exit 6/session halt, no GPU fault. | refused; capture fit insufficient |
| R27 / 133 | 145 / 1 planned | xpu:3/serial; eager planned | legacy | 60 / idle / 1 / background; `text-shift`, `split36` planned | `s133-live01` planned; absent | — | 0 / 0 | — | — | — | CPU-only; native unmeasured | Sealed rehearsal `ModuleNotFoundError: text_residency133`; before device work (CURRENT 14:05). | never launched; repaired in 133b |
| R28 / 133b session 1 | 145 / 1 | xpu:3/serial; eager | legacy | 60 / idle / 1 / background; `text-shift`, `split36` | `s133b-live01` | `94cd0653ca49` | 73 / 64 | 5.225 / 5.555 / 5.859 | 5.186 / 5.554 | 0.871 | 73/73 ← s129-live04; separate seven-field audit 31/31 | Storage guard halted request 73: “Run storage refuses multiply linked files”; path/count unknown. Exit 6; no GPU fault. | faster; halted, not clean production best |
| R29 / 133b session 2 | 145 / 1 | xpu:3/serial; eager | legacy | 60 / idle / 1 / background; `text-shift`, `split36` | `s133b-live02` | `c6df29bb659a` | 232 / 222 | 5.390 / 5.865 / 6.072 | 5.337 / 5.697 | 0.898 | 215/215 ← s129-live04 | Controlled stop at 15:27:09.930 UTC for 135; no client failure/halt. | clean repeat; faster than 129 |
| R30 / 134 arm C | 169 / 0 planned | xpu:3/serial; eager planned | legacy | 60 / idle / 1 / background; `split36` planned | — | — | 0 / 0 | — | — | — | CPU-only; native unmeasured | Sealed; no launch. Only graph-off arm clears conservative census. | diagnostic only; forecast is not a measurement |
| R31 / 135 **best clean / production** | 145 / 1 | xpu:3/serial; eager | legacy | 60 / idle / 1 / background; `text-shift`, `split36` | `s135-live01` | `7ca7bbdde174` | 121 / 111 | **5.248 / 5.727 / 5.919** | 5.210 / 5.529 | **0.875** | 121/121 ← s133b-live02 | Controlled stop at 15:52:11.982 UTC for GC10 A/B; no storage halt or client failure. | best clean completed line; storage repair exercised |
| R32 / 135 GC10 A/B | 145 / 1 | xpu:3/serial; eager | legacy | 10 / idle / 1 / background; `text-shift`, `split36` | `s135-gc10-live01` | pending | 0 / 0 at cutoff | — | — | — | Not yet qualified in captured prefix | Q04 submitted 16:04:42.247 UTC after Q01–Q03 completed; no stop in captured prefix. | **in progress**; no speed verdict |

## Run identities

Each exact directory below is relative to `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/`. It contains `stream-qualification-verdict.json` for completed gates; the verdict ID above is that file's SHA256 prefix. The original JSON retains paths/hashes for its first capture; extension identities are below. Client log headers contain the original name before archive suffixes. Refused rows retain failure/halt evidence and have no pass verdict. Unlaunched rows have no native run directory.

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
| R24 | `encoder-server-continuation-stream-129-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-gc60-ssbackground-sdc1-mi.completed-20261010T114323Z` |
| R25 | `encoder-server-continuation-stream-131-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-ddxpu2-gc60-ssbackground-sdc1-mi-cmreplica-release` |
| R26 | `encoder-server-continuation-stream-132-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-ddxpu2-gc60-ssbackground-sdc1-mi-cmreplica-release-audioxpu2` |
| R27 | No native run; `s133-live01` was planned but absent. Source: CURRENT 14:05 UTC and sealed-import repair note. |
| R28 | `encoder-server-continuation-stream-133b-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-gc60-ssbackground-sdc1-mi-cmtext-shift-textsplit36.completed-20261010T145013Z` |
| R29 | `encoder-server-continuation-stream-133b-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-gc60-ssbackground-sdc1-mi-cmtext-shift-textsplit36` |
| R30 | No native run; `prepared-continuation-stream-134` is a sealed build, not a result. |
| R31 | `encoder-server-continuation-stream-135-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-gc60-ssbackground-sdc1-mi-cmtext-shift-textsplit36` |
| R32 | `encoder-server-continuation-stream-135-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-ssbackground-sdc1-mi-cmtext-shift-textsplit36` |

## Refusals, reliability fixes and unlaunched work

The 117/121 dg1 qualification refused with xpu:3 free 9,587,769,344 B below the unchanged 9,663,676,416 B floor. The 127/169 replica attempt refused with xpu:2 free 8,465,399,808 B below 6.5 GiB transient reserve plus the 2 GiB floor. Neither was a GPU fault or an exactness failure. Including the existing 0.75 GiB screening margin, the latter needs **1.366 GiB** reclaimed, not merely the 0.616 GiB in the immediate floor comparison. The first GC60 rehearsal was rejected by launch scope and did not launch another server. See [169 inventory](../experiments/ltx25-b70/notes/2026-10-10-xpu2-residency-169.md).

The 121 preview and 127 decode-record incidents were writer/reader evidence races. The guard stopped the client while the server chain remained intact. Packet 123 made preview publication atomic; packet 129 extends temp-write/fsync/rename to every route-read evidence file. Packet 121's storage stop charged all filesystem writers to the run's 3 GiB allowance; 123b counts only run-owned writes, and the measured launches use a 16 GiB allowance. The separate 50 GiB filesystem reserve remains. The 123b client initially pinned the outer plan-file hash instead of its inner plan hash, then qualified after correction. These are recorded incidents, not grounds to discard the failed arms.

| Packet | Disposition at cutoff | Evidence |
| --- | --- | --- |
| 118 | CPU review blocked; withdrawn, never launched. Snapshot memory-verdict/schedule checks and pool-cap retention corrected in 118b. | [review](../experiments/ltx25-b70/notes/2026-10-09-continuation118-review.md), [rebuild](../experiments/ltx25-b70/notes/2026-10-09-continuation118b-rebuild.md) |
| 122 | Census/reserve refinement only; no native launch. 145 dg1 and 169 stayed behind memory admission. | [145 census](../experiments/ltx25-b70/notes/2026-10-10-continuation121-results-145.md) |
| 123 | CPU prepared; never launched separately. Preview/residency work inherited by 123b. | [design](../experiments/ltx25-b70/notes/2026-10-10-continuation123-stream-design.md) |
| 130 | CPU sealed; 169 guarded allocator release unmeasured, no launch. | [design](../experiments/ltx25-b70/notes/2026-10-10-continuation130-stream-design.md) |
| 131 | Native first-capture refusal (R25); no streamed result. The allocator release freed zero bytes on xpu:3. Full snapshots retained. | [design](../experiments/ltx25-b70/notes/2026-10-10-continuation131-stream-design.md), [snapshot decision](../experiments/ltx25-b70/notes/2026-10-10-continuation131-snapshot-schedule.md) |

The 132 halt is a **conditioning-B-before** floor refusal during qualification, not a successful stream or an initial request-before refusal. The client and `stream-halt.json` record a halted session even though CURRENT's first summary says “no latch”; no GPU fault is recorded. Its seven completed qualification pairs do not constitute a full verdict. The measured retained cone reservation grew **3.545 GiB**, not the earlier 4.506 GiB estimate; neither is a peak bound that permits reducing the 5 GiB reserve.

Packet 133's author-tree tests missed a sealed-launcher import path defect. 133b bundles the unchanged helper and pinned text oracle beside the launcher, with sealed-import tests. Packet 134 remains sealed, never launched: under split36, only graph-off arm C clears the census. Its **6.50–6.95 s per seven seconds** is a forecast, not a table measurement or a reason to replace the 145 line.

The 133b session-1 guard rejected `st_nlink != 1`, including zero links. Its message does **not** establish a hard link: the offending path and count were not recorded. A CPU deletion-race reproduction makes removal of a consumed preview plausible, not proven. Packet 135 records path/link evidence, waits once for 10 ms and rescans, counts internal links once per inode, and refuses external links. The allowance, 50 GiB reserve and write margin remain unchanged. Its GC60 session completed without a storage halt.

Sources: [132 memory audit](../experiments/ltx25-b70/notes/2026-10-10-continuation132-memory-evidence.md), [133b import repair](../experiments/ltx25-b70/notes/2026-10-10-continuation133b-rebuild.md), [145 results and 169 census](../experiments/ltx25-b70/notes/2026-10-10-continuation133b-results-145.md), [134 design](../experiments/ltx25-b70/notes/2026-10-10-continuation134-stream-design.md), [135 storage evidence](../experiments/ltx25-b70/notes/2026-10-10-continuation135-stream-design.md).

Build receipts pin the packet identities and CPU checks, not native performance:
[117](../experiments/ltx25-b70/data/resume-20261008/continuation117-build.json) [118](../experiments/ltx25-b70/data/resume-20261008/continuation118-build.json) [118b](../experiments/ltx25-b70/data/resume-20261008/continuation118b-build.json) [119](../experiments/ltx25-b70/data/resume-20261008/continuation119-build.json) [120](../experiments/ltx25-b70/data/resume-20261008/continuation120-build.json) [121](../experiments/ltx25-b70/data/resume-20261008/continuation121-build.json) [122](../experiments/ltx25-b70/data/resume-20261008/continuation122-build.json) [123](../experiments/ltx25-b70/data/resume-20261008/continuation123-build.json) [123b](../experiments/ltx25-b70/data/resume-20261008/continuation123b-build.json) [124](../experiments/ltx25-b70/data/resume-20261008/continuation124-build.json) [125](../experiments/ltx25-b70/data/resume-20261008/continuation125-build.json) [126](../experiments/ltx25-b70/data/resume-20261008/continuation126-build.json) [127](../experiments/ltx25-b70/data/resume-20261008/continuation127-build.json) [128](../experiments/ltx25-b70/data/resume-20261008/continuation128-build.json) [129](../experiments/ltx25-b70/data/resume-20261008/continuation129-build.json) [130](../experiments/ltx25-b70/data/resume-20261008/continuation130-build.json) [131](../experiments/ltx25-b70/data/resume-20261008/continuation131-build.json) [132](../experiments/ltx25-b70/data/resume-20261008/continuation132-build.json) [133](../experiments/ltx25-b70/data/resume-20261008/continuation133-build.json) [133b](../experiments/ltx25-b70/data/resume-20261008/continuation133b-build.json) [134](../experiments/ltx25-b70/data/resume-20261008/continuation134-build.json) [135](../experiments/ltx25-b70/data/resume-20261008/continuation135-build.json).

The campaign note preserves the four corrected readings: dg1's apparent graph-contention story versus the later near-floor dual-walk evidence; auxiliary-placement cost mixed with 123b bookkeeping; GC plus allocator cleanup rather than interval alone; and optimistic 169 xpu:2 census margins. Open items are 169 only as the sealed graph-off diagnostic arm, the in-progress 135 GC10 A/B, the owner's snapshot-schedule decision, Flash-Next probes awaiting the owner, and the storage cleanup proposal awaiting the owner. No such action was taken here.

`results/scoreboard.md` contained no LTX row at this audit and is unchanged. This is a durable campaign ledger, not a new public deployment package or promoted benchmark.

## Recompute without changing evidence

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B scripts/analyze-ltx-continuation-ledger.py
```

The command writes JSON to stdout only and reads the sources as they exist when invoked; it does not recreate the historical cutoff from growing logs. Its packet filter predates 132–135. The checked-in snapshot covers the saved logs through packet 129's clean stop at 2026-10-10 11:26:21.736 UTC, packet 131's first qualification request at 11:32:09.449 UTC, and CURRENT through the 11:35 UTC entry. The JSON embeds 131's captured client-log prefix and marks that source as able to grow. If later results appear, compare source hashes and record a new snapshot rather than silently treating them as this cutoff.


### Extension source boundary and read-only recomputation

The GC10 prefix is exactly **1,177 bytes / nine lines**, ending at Q04
submission, 16:04:42.247 UTC after Q01–Q03 completed. It may grow; later bytes are outside this snapshot.
The completed/refused client logs and manifests below were read without changing
them. Directory identities above bind the verdict and halt records. No new
media or tensor files were read for the manifest comparisons.

| Work directory | client.log SHA256 | manifest.jsonl SHA256 |
| --- | --- | --- |
| `s131-live01` | `4b99beceb8169939ccea197e9601c5d01351ed255cfec9b151466f47267bb17e` | `absent` |
| `s132-live01` | `e7bc889479217e674183df412a4db7f39be0ed90da36cb0e07cd58d9f852ce0b` | `absent` |
| `s133b-live01` | `dd1313b09c48e50a43b34b28d14df2e100c5b10393dc90d4e901434eab37d7cf` | `d87e3dc618c022e33199bcf53559ca49b8f5d768c5a9c9431c3ecf6b0dc82c70` |
| `s133b-live02` | `f04426baa43447bc40d51bcccf812167f4e35577d0f180d742e93c2947e7f286` | `ebe3b335c30e09dd9a8f273948f1447abc379fa635a8cba475d26ccf595e2e7c` |
| `s135-live01` | `7b9b873826690571454c20fee85d6bea7d064617dd583a4cad2d776d8f4296ae` | `0d589d8bee9f9ce1f493e72fd1433897eb1966c9ea210ed4bc91f7b4e6013b1c` |
| `s135-gc10-live01` | `5176c41c3856cfacf3f581760be08022f8fc7eb34f5195d2ccd0c74c9cf3e310` (prefix only) | `absent at cutoff` |

The comparison reference `s129-live04/manifest.jsonl` has SHA256
`859aecbaa0400787822c84364396dc0aa877378da4999b5f161405eb82d65837` (215 committed rows). Its saved run directory is
`encoder-server-continuation-stream-129-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-gc60-ssbackground-sdc1-mi`
under the same bench-results root. The new 73/73 and 215/215 comparisons check
matching stream sequence, frames, scene and seed, then all four nonempty digest
fields named in the measurement rules. The seven-field 31/31 result remains
separately scoped to the linked 133b audit.

For the extension, this standard-library-only command prints statistics from
current saved bytes. Check hashes above before treating output as this snapshot.
It retains the submission before the 133b halt. These logs each contain one
client invocation and do not cross midnight; assertions prevent bridging either.
Refused, unlaunched and pre-stream rows have no periods.

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B - <<'PY'
from pathlib import Path
import re, statistics, math
from decimal import Decimal
for name in ('s133b-live01', 's133b-live02', 's135-live01', 's135-gc10-live01'):
    text = (Path('/home/steve/ltx-stream') / name / 'client.log').read_text()
    assert len(re.findall(r'^\[c112 .*?\] server ', text, re.M)) == 1
    events = []
    for h, m, sec, seq in re.findall(
        r'\[c112 (\d+):(\d+):([\d.]+)\] submitted stream\w+-s(\d+)', text):
        events.append((int(seq), Decimal(h)*3600 + Decimal(m)*60 + Decimal(sec)))
    assert all(b[1] >= a[1] for a, b in zip(events, events[1:]))
    rows = [(q, t-pt) for (pq, pt), (q, t) in zip(events, events[1:])
            if q == pq+1 and q >= 10]
    if not rows:
        print(name, 'no measured periods'); continue
    values = sorted(v for q, v in rows)
    print(name, 'n', len(rows), 'median/mean/p90', statistics.median(values),
          statistics.mean(values), values[math.ceil(.9*len(values))-1],
          'even/odd', *(statistics.median([v for q, v in rows if q % 2 == p])
                        for p in (0, 1)))
PY
```
