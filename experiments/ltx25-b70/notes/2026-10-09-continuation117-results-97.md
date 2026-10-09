# Packet 117 at 97 frames: cone anchor decode + stage-B encode overlap + prep-ahead (2026-10-09 01:08–01:27 UTC)

Boot 4aafe57b (owner reboot after the 2026-10-08 Flash-Next attempt-7 fault; kernel 7.0.0-39, fence active,
zero xe fault lines before, during and after this run). Fresh four-card receipt
`data/resume-20261008/postflight-reboot-20261008T2101Z.json`. Launch: `recovery/20261008-continuation117-stream/launch-117.sh
97 frame 1 cone 1 1 <receipt>` (rehearsed with `--check-only` first), unit `ltx117-stream-server-20261008`, run
`encoder-server-continuation-stream-117-frame-dg1-adcone-bo1-pa1-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97`.
Client `stream/start-client-117.sh 97 cone 1 1` (work dir /home/steve/ltx-stream/s117-stream01, 134 chunks, clean stop).

## Qualification: passed, every lever exact

- `stream-qualification-verdict.json`: `passed: true`; exact replay c0/c1/c2 all identical (latents, anchor file,
  images, waveform); verdict 76a9153848bd.
- Lever rows exactly as predicted in LAUNCH.md §5: anchor_decode `full ×3, cone ×6`, `cone_equal` true on all six
  cone chunks; sources `{A: native, B: native}` on eager chunks 1–2, `{A: precomputed, B: precomputed}` on graph and
  repeat chunks 1–2; `dual_equal {A: true, B: true}` on graph chunks 1–2; no anchor-decode, precompute or decoder-graph
  failures. Decoder graph: `new_captures 0,0,0,2,0,0,0,0,0`, reference_equal true on the graph chain.
- Reference check: the eager chain (levers off) equals `stream114-qeager-c00000{0,1,2}` byte for byte on all seven
  tensors (anchor file, audio latent, images, last frame, stage-A latent, video latent, waveform).
- `stream-geometry-measured.json` matches.
- Stream bytes: all 62 chunks that 116b produced from the same seeds (`s116b-frame97-dg1`) are byte-identical in
  `images_sha256` and `anchor_sha256` to 117's chunks 0–61. The 117 levers changed no output byte.

## Stream cadence (medians over chunks 10–109, 100 chunks; 116b in brackets)

| item | 117 (97 f) | prediction | 116b |
|---|---|---|---|
| period, submit to submit | **4.82 s** (4.55–5.34) | 4.35–4.9 | 5.54 |
| submit → anchor ready | 4.47 | | 5.4 |
| `submit_to_sampler_start` | 0.51 (0.48–0.94) | 0.33–0.40 | 0.435 |
| sampler A bucket | 2.02 | | 1.62 + 0.27 cond |
| sampler B | 1.20 | | 1.195 |
| `stage_b_done_to_anchor_ready` | 0.73 | | 1.60 |
| anchor decode in chain (cone) | **0.69** | 0.65–0.95 | 1.57 (full) |
| display decode off-chain | 1.55 | 1.5–1.7 | — |
| precompute A / B (decode thread) | 0.27 / 0.15 | | — |
| precompute waits A / B | 0.00 / 0.00 | ≈0 | — |
| `anchor_ready_to_go` | 0.80 | | — |
| submit → preview written | 8.36 | | — |
| work per second of video | **1.19 s/s** | 1.08–1.21 | 1.37 |

`schedule.go = sampler-a-start` on every chunk; `cone_equal` true on all 100 stream chunks (the full display decode's
last frame equals the cone anchor every time). xpu:3 free before every decode 12.09 GB (floor 9.66); xpu:0 10.37 GB
before stage B (floor 8.59); xpu:3 after 9.92 GB.

Where the 0.72 s came from: the cone decode saved 0.88 s on the chain; `submit_to_sampler_start` did not drop
(0.51 vs 0.435, prediction 0.33–0.40) and the sampler-A bucket grew by ≈0.13 s, so prep-ahead and the stage-B
overlap bought less than designed. The precomputed encodes are never waited for (0.00), so the cost is elsewhere in
the submit→sampler-A path (receipt commit, text window, A-prep consumption): the next 117-code lever is to split
`submit_to_sampler_start` in the receipt.

## Seams

Same metric as 116b (`sharpness_first_frames_min`, min over frames 0–10 relative to frame 48): over the same chunks
the two runs are identical by construction (same bytes). Over chunks 10–109: median 0.946, p25 0.571, 46 % of chunks
below 0.87 and 35 % below 0.7. Over 116b's 62 chunks: median 0.975, p25 0.720, 40 % < 0.87. The low tail is
scene-dependent (dark or low-texture scenes have a noisy relative measure: single-chunk values 0.08–11), not a
packet effect; the owner seam view (`recovery/20261008-continuation115-stream/owner_seam_view.py`) is the honest
check and is unchanged at 97 frames.

## Verdict

Win: 5.54 → 4.82 s per 4.04 s chunk (−13 %), 1.37 → 1.19 s of work per second of video, output bytes unchanged,
every lever exact and in use. Target (≤4.4 s) missed by 0.4 s. Next: 121-frame chunks on the same levers
(prediction 5.2–5.8 s per 5.04 s, 1.03–1.15 s/s), then the full/0/0 control if the split is ambiguous.
