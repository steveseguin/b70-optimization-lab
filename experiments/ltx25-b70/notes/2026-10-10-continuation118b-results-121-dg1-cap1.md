# Packet 118b at 121 frames, decoder graph on with pool cap 1.0 (2026-10-10 02:01–02:12 UTC): exact, but a loss on the period

Boot 4aafe57b. Health receipt `postflight-pre118b-dg1-20261010T0157Z.json`; launched 02:01:15 UTC after the dg0 run's
controlled stop (01:56:10) and the five-minute gap; run
`encoder-server-continuation-stream-118b-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121`;
client `start-client-118b.sh 121 1 cone 1 1 fingerprint 1.0` (work dir `/home/steve/ltx-stream/s118b-dg1-live01`).
Controlled stop 02:12:41 UTC after 37 chunks; no fault line. Names archived under
`output/archive-stream118b-f121-dg1cap1-live-20261010T021306Z`.

## Qualification and the cap

Verdict 493c3b66a3ec at 02:09:07 UTC: `passed`, exact replay c0/c1/c2 identical, dual snapshots agreed, no latch. The
bounded pool did what the design said: `forward_pre_diffusion` was captured (reserved 17.03 → 20.46 GB on the capture),
its growth exceeded the 1.0 GB cap, so `forward_diff_step` stayed eager with the same caches for the life of the server
(`stream-freeze.json`: one capture; `decoder_graph_rows[].pool.cap_bytes = 1e9`). The xpu:3 floor held where 117's
uncapped dg1 had refused by 76 MB; the minimum snapshot margin was 0.76 GB (dg0: 1.45 GB). `cone_equal` true on 37/37.

## Cadence (medians, chunks 10–36; dg0 run of the same night in brackets)

| bucket (client receipt line) | dg1 cap 1.0 | dg0 |
|---|---|---|
| **period, submit to submit** | **5.559 s** (5.25–6.25) per 5.04 s of video = 1.10 s/s | **5.227 s** = 1.037 s/s |
| anchor-decode on the chain (cone) | 0.76 (graph) | 0.96 (eager) |
| display decode off the chain | 2.12 (graph) | 2.65 (eager) |
| upsample + stage-B prep | **0.80** | **0.28** |
| text + A-prep | 0.50 | 0.49 |
| sampler A / sampler B | 1.755 / 1.33 | 1.77 / 1.38 |
| go-wait (off-chain) | 0.76 | 0.93 |

The graph saved 0.19 s on the chain (cone) and 0.53 s off it (display), and cost 0.52 s on the chain in the stage-B
bucket: net +0.33 s per chunk. Hypothesis (to be verified from the precompute-B and stage-B snapshot timestamps against
the display-decode start/end): the display decode's graph replay is one large submission on xpu:3, and on a B70 all
queues serialize into the single compute queue, so stage B's xpu:3 work (its two xpu:3 snapshots, which synchronize,
and the in-place image-to-video node) waits behind the whole replay, whereas the eager decode interleaves kernel by
kernel and lets stage B through. Consistent with the earlier finding that compute/compute overlap does not exist on
this card.

## Verdict and next

**Loss; dg0 stays the live line.** Keep the lever available (it is exact) and attack the scheduling instead: start the
display decode only after stage B's xpu:3 work has been submitted, or run it on the decode replica device, so the cone
gain (−0.19 s) is kept without the stage-B penalty (+0.52 s). That is lever A of the packet-119 design brief, together
with prep-ahead of the anchor read / text window (0.12 s) and an owner-decided snapshot schedule option (0.20 s on the
chain in three four-card synchronizes).
