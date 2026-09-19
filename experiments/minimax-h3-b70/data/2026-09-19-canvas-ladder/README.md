# MiniMax-H3 canvas ladder, 2026-09-19 18:46-19:03 EDT: receipts

The batch window that walked the canvas from the 448x256 smoke size up to **960x544, the resolution
this checkpoint was trained for**, and ran the INT8 denoiser there too. Three GPU runs, all rc 0,
**zero `xe` fault lines**, same boot as the two earlier windows. Driver
`/mnt/fast-ai/bench-results/batch3-session-20260919.sh`; the narrative, the scaling fits and the
speed levers are in the
[first-light note](../../notes/2026-09-19-first-light.md#canvas-ladder-2246-2259-utc).

All three runs: 124 frames, 9 grid points (8 NFE), seed 42, turbo LoRA, `pread` loader,
`B70_H3_XFER=host`, `PYTORCH_ALLOC_CONF=expandable_segments:True`, VAE tiling on, under
`mem-watchdog.sh`. Only the canvas and the denoiser vary.

**Outcome: the trained canvas fits with room to spare.** At 19,348 packed rows the pruned run peaked
with **8.4 GiB free** on the tighter card and live activations only 0.21 GiB above the 448x256 run --
so the memory plan's "~80 GiB per card if attention is materialized" bound never applied. `sample`
fits `t = 3.256e-3*n + 1.232e-7*n^2` to within 1.2 % across the ladder (**attention is 42 % of
denoising at 960x544**, against 15 % at 448x256), and `decode.video` is now the fastest-growing
phase at 11 -> 32 -> 80 s, running on one card in float32 while the other holds nothing.

| File | What it is |
| --- | --- |
| `receipt-smoke-20260919T224743Z-pruned-576x320.json` | The intermediate rung. Pruned BF16, 576x320, 7,138 packed rows. `sample` 29.18 s, `decode.video` 31.89 s, end to end 116.3 s. Per-card peaks, the split plan, host peak RSS and the four output hashes. |
| `receipt-smoke-20260919T224948Z-pruned-960x544.json` | **The trained canvas, pruned BF16.** 19,348 packed rows. `sample` 109.10 s (13.63 s/step), `decode.video` 79.96 s, end to end 243.8 s, 47.18 s of wall per second of video. After `sample`: allocated 19.012 / 18.955 GiB, reserved 22.734 / 22.395, free 8.406 / 9.133. |
| `receipt-smoke-20260919T225400Z-int8-960x544.json` | **The trained canvas, INT8 ConvRot.** Same canvas and seed. `sample` 152.87 s (+40 % on the pruned path, against +74 % at 448x256), `decode.video` 80.02 s -- identical, as it must be, since the decode never sees the denoiser. Reserved climbs to 26.688 / 26.137 GiB with only **4.465 / 5.388 GiB free**: allocator cache for the per-step dequantized weights, and the ceiling any INT8 speed lever works under. |
| `batch3-session-20260919.log` | The window's full transcript: the service stop, the two-card XPU/XCCL health probe, all three runs with their `[phase]` and `[vram]` lines and per-step progress, the watchdog summaries, then the service restart that is [validation start 2](../../../qwen38-27b-b70/data/2026-09-19-service-start-noswap-2/) of the no-swap change. |

## Where the clips are

Not copied here: `*.mp4` and `*.safetensors` are Git-ignored, and each run's `tensors.safetensors` is
265-750 MB. They live under `/mnt/fast-ai/bench-results/minimax-h3-canvas-20260919/`:

| Path | Clip |
| --- | --- |
| `pruned-576x320/smoke-20260919T224743Z/clip.mp4` | pruned BF16, 576x320, 763,710 bytes |
| `pruned-960x544/smoke-20260919T224948Z/clip.mp4` | **pruned BF16 at the trained 960x544**, 3,106,978 bytes |
| `int8-960x544/smoke-20260919T225400Z/clip.mp4` | **INT8 ConvRot at the trained 960x544**, 4,891,803 bytes |

Every clip is h264, 124 frames, 5.167 s at 24 fps, with AAC 32 kHz stereo of 5.175 s. Each directory
also holds its own `receipt.json` (copied here) and `tensors.safetensors` (not copied); the per-run
stdout log and the watchdog log sit beside each directory as
`smoke-<stamp>.log` and `smoke-<stamp>.watchdog.log`.

Frame 62 of both 960x544 clips is a rain-slicked night street with neon reflections and an umbrella
figure walking away from camera; the INT8 one shows more scene detail and a more prominent subject.
**Two frames of one prompt is not a quality verdict** -- the sampler decorrelates under any weight
change, so these are two different draws of the same scene.
