# Packet 123b at 169 frames (aux residency on xpu:2, dg0, display xpu:3), 2026-10-10 06:15–06:33 UTC: exact, 0.975 s/s, a loss against 145

Launched 06:15 UTC (`LTX_AUX_RESIDENCY=xpu2 LTX_RUN_WRITE_ALLOWANCE_GIB=16 launch-123b.sh 169 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3`),
health receipt `postflight-pre123b-f169-…`, run `encoder-server-continuation-stream-123b-frame-dg0-adcone-bo1-pa1-smfp-…-f169`, work dir
`/home/steve/ltx-stream/s123b-f169-live01`. Qualification verdict 4eeb3b603c94 at 06:24:29 UTC: `passed`, exact replay c0/c1/c2 identical
(no earlier reference at 169; three-chain identity is the gate), geometry 169 frames = 168 new frames = 7.0 s of video. ≈ 40 chunks streamed,
`cone_equal` true on all, no fault, no latch. Controlled stop 06:33 UTC; the 145-frame aux line relaunched.

## Cadence (chunks ≥ 10, n = 27; 145-frame aux line in brackets)

| item | 169 f | 145 f (aux) |
|---|---|---|
| **period, median** | **6.824 s** (mean 6.95) per 7.0 s = **0.975 s/s** | 5.73 s per 6.0 s = **0.955** (legacy placement 0.939) |
| sampler A / B | 1.98 / 1.85 | 1.91 / 1.62 |
| cone anchor decode on the chain | **1.73** | 1.02 |
| display decode off the chain (eager, xpu:3) | **3.98** (bound 3 s; forecast 2.72–3.30) | 2.75 |
| go-wait (off-chain) | 1.06 | |
| text + A-prep / upsample + B-prep / receipt | 0.54 / 0.33 / 0.12 | 0.52 / 0.33 / 0.11 |
| min snapshot margin / dual | 1.93 GB / periodic | 1.98 GB / periodic |

## Reading

Memory was fine (the residency move did its job: 1.93 GB minimum margin, no near-floor duals). The loss is on xpu:3's compute queue:
the eager display decode grew to 3.98 s (over the 3 s bound; the decoder's cost scales faster than frames at this length) and the cone decode
on the chain rose from 1.02 to 1.73 s, i.e. the cone waits behind the previous chunk's display decode on the same card. The sampler scaled
sublinearly as before (A+B 3.83 s for +17 % frames), so the chunk-length lever is still worth having if the display decode leaves xpu:3.

## Next

Packet 124 (Codex): the 169 arm with the display decode off xpu:3 within memory: display replica on xpu:2 with the auxiliary residency
elsewhere (xpu:1 has 1.6–1.8 GiB; or keep aux legacy if the measured 145/169 margins on xpu:0 now admit it), or a split/deferred display
decode that never overlaps the next cone. Until then the live line is 123b at 145 frames (aux xpu:2).
