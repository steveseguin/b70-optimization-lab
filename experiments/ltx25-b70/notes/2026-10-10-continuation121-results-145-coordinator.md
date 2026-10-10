# Packet 121 at 145 frames, dg0, display on xpu:3 (2026-10-10 04:09 UTC →): 5.64 s per 6.0 s of video = 0.94 s/s, exact

Coordinator's live summary (Codex's receipt analysis follows in `2026-10-10-continuation121-results-145.md`).
Boot 4aafe57b. Health receipt `postflight-pre121-20261010T040508Z.json` (see data/resume-20261008). Launched 04:08:58 UTC after
the controlled stop of the 120 session (135 chunks, 1.008 s/s): `launch-121.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3`,
run `encoder-server-continuation-stream-121-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145`, client
`start-client-121.sh 145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3` (work dir `/home/steve/ltx-stream/s121-live01`).

## Qualification

Verdict 356b25be584b at 04:17:28 UTC: `passed`, exact replay c0/c1/c2 identical on every tensor, 4 signatures per route; measured
geometry matches the sealed formulas (`stream-geometry-measured.json: matches true`; 145 frames, 144 new frames = 6.0 s of video per
anchored chunk; audio latent `[1,8,151,16]`, waveform `[1,2,288480]`). No earlier reference exists at 145 frames; the three-chain
identity is the gate. No latch.

## Cadence (chunks ≥ 10, n = 86 periods at 04:36 UTC)

| item | 145 f (121, dg0, xpu:3) | 121 f (120) | 121 f (118b dg0) |
|---|---|---|---|
| **period, median** | **5.636 s** (mean 5.77, p90 6.23) per **6.0 s** of video = **0.939 s/s** | 5.082 / 5.042 = 1.008 | 5.263 = 1.044 |
| sampler A / B | 1.91 / 1.68 | 1.78 / 1.33 | 1.78 / 1.39 |
| cone on the chain (eager) | 0.87 | 0.77 (graph) | 0.98 |
| text + A-prep / upsample + B-prep / receipt | 0.51 / 0.29 / 0.10 | 0.49 / 0.28 / 0.10 | 0.49 / 0.28 / 0.09 |
| display decode off-chain (eager, xpu:3) | 2.72 | 2.68 (xpu:2) | 2.68 |
| dual snapshots | periodic only (every 20th chunk) | periodic | periodic |
| minimum snapshot margin | 1.39 GB | 0.77 GB | 1.45 GB |

Stable across 20-chunk windows (medians 5.612 / 5.625 / 5.622 / 5.616); the slowest periods (6.3–6.8 s) are the every-20th dual
snapshot chunks and scene cuts. `cone_equal` true on all chunks. Sink: holds stopped after startup, buffer growing (24 s at 89 clips).

## Reading

The chunk-length step did what the arithmetic said: fixed per-chunk costs (≈ 1.3 s) amortise over 6.0 s instead of 5.04 s, and the
sampler scaled sublinearly (A+B 3.59 s for +20 % frames, from 3.17). This is the first line under real time with margin.

## Next

1. 145 frames with 120's structure (dg1 cap 1.0, eager display on the xpu:2 replica): cone −0.1 to −0.2 s → ≈ 0.90–0.92 s/s, once
   Codex's 145/169 census (packet 122) confirms the replica transient budget and the graph-pool margin at 145.
2. 169 frames (7.0 s of video) if the refined census clears every floor with the 0.5 GiB near-floor band.
