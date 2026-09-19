# MiniMax-H3 first light, 2026-09-19 18:16-18:28 EDT: receipts

The batch window in which the lane first rendered a clip, passed the bytewise repeat gate and ran
the INT8-vs-pruned A/B. Four runs, all rc 0, zero `xe` fault lines. Driver
`/mnt/fast-ai/bench-results/batch2-session-20260919.sh`; the narrative and the analysis are in the
[first-light note](../../notes/2026-09-19-first-light.md).

All four runs: 448x256, 124 frames, 9 grid points (8 NFE), seed 42, turbo LoRA, `pread` loader,
`B70_H3_XFER=host`, `PYTORCH_ALLOC_CONF=expandable_segments:True`, under `mem-watchdog.sh`. The
only setting that varies is the denoiser.

| File | What it is |
| --- | --- |
| `receipt-smoke-20260919T221709Z-pruned.json` | **First light.** Pruned BF16 denoiser split at block 24. Per-phase timings, per-card peak allocated/reserved, the split plan, host peak RSS, and the four output hashes. `sample` 17.68 s, `decode.video` 11.12 s, `encode` peak 25.53 GiB on xpu:0, `decode.video` peak 10.42 GiB on xpu:1. |
| `receipt-repeat-20260919T221840Z-a.json` | Repeat gate, run A. Same seed, same everything. |
| `receipt-repeat-20260919T221840Z-b.json` | Repeat gate, run B. All four hashes match run A and the first-light run: `REPEAT GATE: bytewise-equal`. |
| `receipt-smoke-20260919T222143Z-int8.json` | The INT8 ConvRot denoiser, `B70_H3_DENOISER=int8`, LoRA applied at runtime as the additive low-rank term. `sample` 30.80 s (1.74x the pruned path), `load.stream` 18.95 s (faster), residency 16.05 / 15.65 GiB. |
| `int8-vs-pruned.json` | `compare-h3-runs.py` output: receipt-hash comparison, whole-tensor max/mean absolute difference and differing fraction for video, audio and both latent tensors, then the same per frame for all 124 frames. Everything differs; 124/124 frames differ. **Nonzero is expected** -- the two builds quantize different things and the sampler decorrelates -- so read it as "two different clips of the same scene", not as an error bar. |
| `session.log` | The batch window's full transcript: preconditions, the two-card XPU/XCCL health probe, all four runs with their `[phase]` and `[vram]` lines, the watchdog summaries, the `MATCH` lines of the repeat gate and the frame-by-frame comparison table. |

## Where the clips are

Not copied here: `*.mp4` and `*.safetensors` are Git-ignored, and each run's
`tensors.safetensors` is 173.6 MB. They live under
`/mnt/fast-ai/bench-results/resume-20260919d/minimax/`:

| Path | Clip |
| --- | --- |
| `smoke-20260919T221709Z/clip.mp4` | first light, pruned BF16, 857,159 bytes |
| `repeat-20260919T221840Z-a/clip.mp4` | repeat gate run A, byte-identical to the above |
| `repeat-20260919T221840Z-b/clip.mp4` | repeat gate run B, byte-identical to the above |
| `smoke-20260919T222143Z/clip.mp4` | INT8 ConvRot, 1,041,665 bytes |

Every clip is h264 448x256, 124 frames, 5.167 s at 24 fps, with AAC 32 kHz stereo of 5.175 s. Each
directory also holds its own `receipt.json` (copied here) and `tensors.safetensors` (not copied).

Raw session root, with the per-run logs, the watchdog logs, the health log and
`int8-vs-pruned.log`: `/mnt/fast-ai/bench-results/resume-20260919d/`.
