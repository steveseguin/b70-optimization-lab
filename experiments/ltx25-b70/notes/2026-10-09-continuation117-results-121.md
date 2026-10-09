# Packet 117 at 121 frames, decoder graph off (2026-10-09 01:58–02:25 UTC): 1.08 s of work per second of video

Boot 4aafe57b; health receipt `postflight-after-probe-fault-20261009T0140Z.json` (taken after the one-card slab-probe
fault at 01:39 UTC, first incident of this boot; kernel fault count unchanged at 2 through this run).

## The dg1 attempt first (01:44–01:52 UTC): refused by the xpu:3 floor, as LAUNCH.md §4 predicted

Run `…-117-frame-dg1-adcone-bo1-pa1-…-f121`: window probe, prepare, eager chain and graph chunk 0 passed; at graph
chunk 1 the stage-A precompute guard refused: xpu:3 physical free 9,587,769,344 B against the 9,663,676,416 B floor
(76 MB short). Graph chunk 0 had 15.83 GB free before its decode (before the two captures); the 121-frame decoder-graph
pool plus the eager cone transient took the rest. The server latched `precompute-117-refused.json`; the client stopped
(exit 6), no retry. Latch archived to `latch-archive/precompute-117-refused-20261009T0152Z-xpu3-floor-121-dg1.json`
with the review receipt `data/resume-20261008/latch-archive-precompute-117-20261009T0152Z-receipt.json`; the run's
`stream117-` names archived under `output/archive-…-f121-dg1-refused-20261009T0144Z/`. Memory guard, not a lever or
exactness failure, no GPU fault.

## The dg0 run (preregistered fallback): qualification passed, 140 chunks

Run `encoder-server-continuation-stream-117-frame-dg0-adcone-bo1-pa1-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121`,
launched 01:58:13 UTC after the five-minute gap (rehearsed with `--check-only`), client
`start-client-117.sh 121 0 cone 1 1`. Verdict cff20f16ae37: `passed`, exact replay c0/c1/c2 identical, cone rows
true ×6, precomputed sources on graph/repeat chunks 1–2, no lever failures; `reference_check: null` at 121 frames
(no earlier reference exists; the three-chain identity is the gate). Geometry matches the sealed formulas:
images `[121,256,256,3]`, video latent `[1,128,16,8,8]`, audio `[1,8,126,16]`, waveform `[1,2,240480]`.

## Cadence (medians over chunks 10–109; 97-frame 117 run in brackets)

| item | 121 f, dg0 | prediction | 97 f, dg1 |
|---|---|---|---|
| period, submit to submit | **5.40 s** (5.13–5.64) per 5.04 s of video | 5.2–5.8 (central 5.35) | 4.82 per 4.04 s |
| work per second of video | **1.08 s/s** | 1.03–1.15 | 1.19 |
| submit → anchor ready | 4.98 | | 4.47 |
| `submit_to_sampler_start` | 0.52 (0.46–0.99) | 0.33–0.40 | 0.51 |
| sampler A bucket | 2.08 | | 2.02 |
| sampler B | 1.38 | | 1.20 |
| cone anchor decode on the chain (eager) | 0.955 | 0.70–1.00 | 0.69 (graph shadow) |
| `stage_b_done_to_anchor_ready` | 0.99 | | 0.73 |
| display decode off-chain (eager) | 2.68 | 1.9–2.2 | 1.55 (graph) |
| precompute A / B | 0.42 / 0.12 | | 0.27 / 0.15 |
| submit → preview written | 10.06 | | 8.36 |
| xpu:3 free before every decode | 15.64 GB (floor 9.66) | ≈15.6 | 12.09 |
| min free before stage B, xpu:0 / xpu:1 | 10.25 / 10.62 GB (floors 8.59) | | 10.37 / 10.72 |

`cone_equal` true on all 100 chunks; `schedule.go = sampler-a-start` on every chunk; no resets. Seams
(`sharpness_first_frames_min`): median 0.899, p25 0.675, 47 % of chunks below 0.87, the same scene-dependent
spread as the 97-frame runs (frame anchor, no latent conditioning). The display decode runs eager at 121 frames
(2.68 s) because the decoder graph is off; it is off the chain and finishes before the next chunk's anchor is
needed (`anchor_ready_to_go` 0.95 s).

## Reading and next lever

Per second of video the chain is now 1.08 s: sampler A + B = 3.46 s of the 5.40 s period (64 %), the cone decode
0.96 s, `submit_to_sampler_start` 0.52 s and the receipt/turnaround 0.42 s. Prep-ahead did not shorten
`submit_to_sampler_start` at either frame count (0.51–0.52 vs 0.435 on 116b), although the precomputed encodes
are never waited for; that bucket is unexplained and is the cheapest 0.2–0.3 s left. Below 1.0 s/s at 121 frames
needs −0.4 s: split `submit_to_sampler_start` and the receipt→next-submit path in the receipt (packet 118 design),
then decide between a 145-frame chunk (the cone fraction keeps falling with length) and a 121-frame dg1 run
with a smaller decoder-graph pool (xpu:3 needs ≈ 0.1 GB more headroom than it has).
