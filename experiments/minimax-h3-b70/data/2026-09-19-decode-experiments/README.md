# MiniMax-H3 decode experiments, 2026-09-19 19:39-19:49 EDT (23:39-23:49 UTC): receipts

Batch window 4. The window that took the two video-decode levers to the cards: **E1** (do the two
B70s decode the same tile to the same bits?), **lever 2** (the two-card tiled VAE decode), and **E2**
(fp16 autocast decode). Six GPU runs plus the CPU tile-loop test, ten minutes of card time, **rc 0
everywhere, zero `xe` fault lines**, the memory watchdog never fired, host MemAvailable low-water
10,232 MiB. The FP8 service was stopped for the window and restarted at the end of it.

Driver: `experiments/minimax-h3-b70/scripts/decode-experiments-session.sh`. Narrative and the
re-ranked levers:
[speed plan](../../notes/2026-09-19-speed-plan.md#results-window-4-2026-09-19-1939-1949-edt) and
[first light](../../notes/2026-09-19-first-light.md#decode-experiments-2339-2345-utc).

Every run decodes **the same latents** — `pruned-960x544/smoke-20260919T224948Z/tensors.safetensors`
from the [canvas ladder](../2026-09-19-canvas-ladder/) — through `--decode-only`, so only the decode
varies: 124 frames at 960x544, seed 42, turbo LoRA, pruned BF16 denoiser, VAE tiling on,
`B70_H3_XFER=host`, `PYTORCH_ALLOC_CONF=expandable_segments:True`, under `mem-watchdog.sh`.

**Outcome in one line: the two-card decode is bit-identical and 1.01x; fp16 autocast is 5.0-5.2x and
not bit-identical.**

| run | decode | `decode.video` | vs source video hash | peak allocated (xpu:0 / xpu:1) |
|-----|--------|---------------:|----------------------|-------------------------------|
| `control-single-off` | single, fp32 | 79.31 s | **identical** | — / 11.878 GiB |
| `two-card-off` | two-card, fp32 | 78.27 s | **identical** | 10.223 / 12.296 GiB |
| `fp16-a` | single, fp16 | 15.93 s | differs | — / 15.050 GiB |
| `fp16-b` | single, fp16 | 15.34 s | differs | — / 15.050 GiB |
| `two-card-fp16` | two-card, fp16 | 16.81 s | differs | 9.873 / 14.922 GiB |

Source run for comparison: `decode.video` 79.96 s,
`video_tensor_sha256 = ac730503b4380001566532ca6e03fb9752250f44488b0dee7c9baff244a35280`.

| File | What it is |
| --- | --- |
| `probe-e1-20260919T233947Z.json` | **E1, and all four gates pass.** Per-tile sha256 per card per pass for 3 tiles x 2 cards x 2 passes: `gates.identity_across_cards: true`, `gates.repeatable_per_card: true`. With both 9.700 GiB VAE replicas up, 9.707 GiB allocated per card (10.223 GiB peak, gate was <= 12.5) and `host_peak_rss_bytes` 9.349 GiB — *below* a normal run's 12.467 GiB, which is the receipt that building copy B through `cross_card()` beats a second `from_pretrained`. Also carries the decode plan (105 tiles, 7 chunks x 15) and the hash of the diffusers VAE source the reimplementation was written against. |
| `receipt-control-single-off-20260919T233947Z.json` | **The control, and the proof that `--decode-only` is honest.** One card, float32, the old code path. `decode.video` 79.308 s and **all four source hashes MATCH** — so decoding saved latents stands in for the decode half of a full run, and every later row is measured against something real. |
| `receipt-two-card-off-20260919T233947Z.json` | **Lever 2, exact and useless.** 105 tiles split 53/52 over xpu:1 and xpu:0, blended on xpu:1, **all four hashes MATCH** — the §1.3 bit-identical-by-construction claim holds on hardware. `decode.video` 78.274 s against 79.308: **1.01x**. The work was divided and the wall time did not move: the two Python worker threads never overlapped. Also records `decode.replicate_vae` 2.576 s, the cost of building copy B. |
| `receipt-fp16-a-20260919T233947Z.json` | **E2 run A.** Single card, `--vae-autocast fp16`. `decode.video` **15.929 s, 4.98x the control**. Video hash differs from the source; audio and both latent hashes MATCH. Peak allocated 15.050 GiB — *higher* than float32's 11.878 GiB, the one E2 gate that failed. |
| `receipt-fp16-b-20260919T233947Z.json` | **E2 run B, the repeat gate.** `decode.video` 15.340 s, and **all four hashes bytewise equal to run A**. fp16 autocast is deterministic on these cards, so E2 measures a different arithmetic, not a random one — without this the fidelity numbers below would be unreadable. |
| `receipt-two-card-fp16-20260919T233947Z.json` | **Both levers together: 16.814 s, slower than single-card fp16.** Same thread serialization plus 2.85 s of replicate. If fp16 becomes the default it is single-card fp16. |
| `vs-control-fp16-a-20260919T233947Z.json` | **The fidelity A/B**, fp16 run A against the float32 control, from `compare-h3-runs.py`: whole-tensor and **per-frame** max/mean absolute difference and differing fraction for all 124 frames. Video `max\|d\| 0.0295003`, `mean\|d\| 0.000115222`, 99.8323 % of values differ, worst frame 120, 124/124 frames differ. Audio, video latents and audio latents all identical, `max\|d\| 0`. |
| `batch4-session-20260919.log` | The window's full transcript: the service stop and health probe, the CPU tile-loop test against upstream's own `_decode` (bitwise equal in all three cases), all six GPU runs with their `[phase]`, `[vram]` and watchdog lines, the summary table, then the service restart that is validation start 3 of the no-swap change (12/12 exact at 89.84 tok/s). |

## Reading the fidelity numbers

The compared tensor is the runner's `video_cpu`, whose range is **[0, 1]** —
`run_h3_t2v.py:4046` un-normalises with the ImageNet mean/std and clamps to (0, 1), and the mp4
writer multiplies by 255 at `run_h3_t2v.py:4075`. **One 8-bit level is therefore 1/255 = 0.003922**,
so:

* `mean|d|` 0.000115222 = **0.029 of one 8-bit level**, about a thirtieth of the smallest difference
  an 8-bit pixel can express;
* `max|d|` 0.0295003 = **7.5 levels of 255**, for the single worst pixel of 66,416,640
  (3 x 124 x 544 x 960), on frame 120.

"99.83 % of values differ" and "0.029 of a level on average" are the same fact twice: nearly every
pixel moves, by much less than the container can record. The mp4 is lossy h264 at crf 16, so the
encoder's own quantisation is larger than this difference everywhere but that worst pixel. **It is
still not bit-identical**, and the receipts say so permanently.

## Not copied here

`*.mp4` and `*.safetensors` are Git-ignored and each run's `tensors.safetensors` is 786 MB. The six
run directories, their clips, tensors, per-run stdout logs and watchdog logs live under
`/mnt/fast-ai/bench-results/minimax-h3-decode-20260919/`:

| Path | What |
| --- | --- |
| `control-single-off-20260919T233947Z/` | the float32 control; `clip.mp4` is byte-for-byte the canvas-ladder clip's decode |
| `two-card-off-20260919T233947Z/` | the bit-identical two-card decode |
| `fp16-a-20260919T233947Z/`, `fp16-b-20260919T233947Z/` | the two fp16 runs, identical to each other |
| `two-card-fp16-20260919T233947Z/` | both levers |
| `e1-probe-20260919T233947Z/` | E1; `probe.json` only, no clip — the probe decodes 3 tiles and exits |

The source latents and the clip they came from are at
`/mnt/fast-ai/bench-results/minimax-h3-canvas-20260919/pruned-960x544/smoke-20260919T224948Z/`.
