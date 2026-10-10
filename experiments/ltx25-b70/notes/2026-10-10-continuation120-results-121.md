# Packet 120 at 121 frames (display decode on an xpu:2 replica, graph cone): 5.08 s per 5.04 s chunk = 1.008 s/s, exact

Boot 4aafe57b. Health receipt `postflight-pre120-20261010T033817Z.json`. Controlled stop of 118b dg0 session 3 at 03:38:17 UTC
(167 chunks, period median 5.263 s), names archived, `--check-only` passed, launched 03:43:18 UTC:
`launch-120.sh 121 frame 1 cone 1 1 fingerprint 1.0 eager-display 0 full xpu:2`, run
`encoder-server-continuation-stream-120-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121`, client
`start-client-120.sh 121 1 cone 1 1 fingerprint 1.0 eager-display 0 full xpu:2` (work dir `/home/steve/ltx-stream/s120-live01`).
Streaming publicly since qualification. Design: `2026-10-10-continuation120-stream-design.md`.

## Qualification

Verdict 0d3305d1a160 at 03:52:06 UTC: `passed`, exact replay c0/c1/c2 identical, the xpu:2 display decode equal to the
xpu:3 uncached eager display on every chain, replica weight copy bitwise equal (`weight_copy_bitwise_equal: true`), dual
snapshots agreed, no latch. Replica residency: 0.83 GB of weights on xpu:2, margin ≈ 5.4 GB above the 2 GiB floor with the
4 GiB transient budget; observed growth per display decode ≈ 3.2 GB.

## Output identity

Against the 118b dg0 session 3 (same scenes, same seeds, chain from seq 0): `images_sha256`, `last_frame_sha256`,
`preview_sha256` **identical on 109/109** chunks. `cone_equal` (xpu:2 display last frame == xpu:3 cone anchor) true on all.

## Cadence (chunks 10–109, 100 periods; 118b dg0 session 3 in brackets)

| item | 120 | 118b dg0 |
|---|---|---|
| **period, submit to submit, median** | **5.082 s** (p10 4.81, p90 5.59, mean 5.14) per 5.0417 s of video = **1.008 s/s** | 5.263 s = 1.044 |
| cone anchor decode on the chain | 0.77 (graph) | 0.98 (eager) |
| upsample + stage-B prep | 0.28 | 0.28 |
| text + A-prep | 0.49 | 0.49 |
| sampler A / B | 1.78 / 1.33 | 1.78 / 1.39 |
| receipt | 0.10 | 0.09 |
| display decode off the chain (xpu:2, eager) | 2.68 | 2.68 (xpu:3) |
| dual (walk + fingerprint) snapshots | 5/99 chunks (the periodic every-20th plus a few near-floor) | periodic |

The first 28 periods read 5.029 (reported at 03:58 UTC as "real time reached"); over 100 periods the median is 5.082, so the
line is **0.8 % above real time**, not at it. The gain over 118b is the cone (−0.21 s) with no stage-B or snapshot penalty,
exactly what the dg1 runs lost to near-floor dual walks before the display transient left xpu:3.

## Next

Packet 121: 145-/169-frame chunks (fixed per-chunk costs ≈ 1.3 s amortise; sampler time grew 7.5 % for +25 % frames from 97
to 121). With the display decode on xpu:2 the xpu:3 budget for longer cones is wider than it was.
