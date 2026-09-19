# MiniMax-H3 first light: the pipeline renders, and it repeats bit for bit (2026-09-19)

Date: 2026-09-19, batch window 2, **18:16-18:28 EDT (22:16-22:28 UTC)**. Host
`steve-TURIND8-2L2T`, two B70s, same boot as the 17:20 EDT two-card service start (no reboot in
between). Driver script `/mnt/fast-ai/bench-results/batch2-session-20260919.sh`, log
`batch2-session-20260919.log`, session root `/mnt/fast-ai/bench-results/resume-20260919d`
(`session.log` there, runs under `minimax/`). **Zero `xe` fault lines all evening.**

> **Update, batch window 3, 18:46-18:59 EDT (22:46-22:59 UTC): the trained 960x544 canvas renders, on
> both denoisers.** Three more runs walked the ladder 576x320 -> 960x544 pruned -> 960x544 INT8, all
> rc 0, still zero fault lines. The plan's ~80 GiB materialized-attention bound never applied. With
> the real canvas measured, the time breakdown changes what is worth optimizing: sampling is 45 % of
> a run, the **video decode is 34 % and runs on one card while the other idles**, and **46 s of every
> run is model loading that does not depend on the prompt**. See
> [Canvas ladder](#canvas-ladder-2246-2259-utc) and
> [Speed levers, none tried yet](#speed-levers-none-tried-yet).

## In plain words

**The video model generated a video.** Four runs in eleven minutes: one clip from the pruned BF16
denoiser split across the two cards, two more at the same seed that came out byte for byte
identical, and one from the INT8 denoiser as a comparison. Every run exited 0, every run wrote a
playable mp4 with sound, and nothing on the host or the cards complained.

The clip is 448x256, 124 frames, 5.17 seconds at 24 frames a second, with 32 kHz stereo audio of
the same length. It takes about **83 seconds of wall time to make 5 seconds of video** -- 16 s of
machine per second of clip -- of which 18 s is the actual denoising and the rest is loading the
text encoder and the denoiser onto the cards and decoding the result back to pixels.

The picture matches what was asked for. The prompt was a rain-slicked city street at night with
neon signs, reflections in puddles and a figure with an umbrella walking away from camera; frame 62
of the pruned clip is exactly that scene.

The two-card run repeats **bit for bit**: three separate runs at seed 42 produced the same four
hashes -- video tensor, audio tensor, video latents, audio latents. That is the gate this lane has
been trying to reach since 2026-09-17, and it is the one that makes every later A/B meaningful,
because a difference between two runs can now only come from the thing that was changed.

The INT8 denoiser also works, produces a different-looking clip of the same scene, and is
**1.7x slower in the denoising phase** (30.8 s against 17.7 s) because every quantized weight has
to be widened to bfloat16 on every step. Which of the two looks better is not something one frame
of one prompt can decide, and this note does not claim it.

---

## The four runs

All four: `run_h3_t2v.py`, 448x256, **124 frames**, **9 grid points = 8 NFE**, seed 42, turbo LoRA
`minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` merged (or, on the int8 path, applied
at runtime as the additive low-rank term), `pread` loader, `B70_H3_XFER=host` (host-staged
cross-card transfers), `PYTORCH_ALLOC_CONF=expandable_segments:True`, VAE tiling on, under
`mem-watchdog.sh` at a 2048 MiB floor. The only setting that differs anywhere in the table is the
denoiser.

| Run | Denoiser | rc | `sample` | `decode.video` | wall / s of video | `clip.mp4` |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `smoke-20260919T221709Z` | pruned BF16 | 0 | **17.68 s** | 11.12 s | 16.11 s | 857,159 B |
| `repeat-20260919T221840Z-a` | pruned BF16 | 0 | 17.72 s | 10.79 s | 16.06 s | 857,159 B |
| `repeat-20260919T221840Z-b` | pruned BF16 | 0 | 17.71 s | 10.80 s | 16.40 s | 857,159 B |
| `smoke-20260919T222143Z` | INT8 ConvRot | 0 | **30.80 s** | 11.42 s | 15.90 s | 1,041,665 B |

`clip.mp4` from the first run: **h264, 448x256, 124 frames, 5.167 s at 24 fps, plus AAC 32 kHz
stereo, 5.175 s**. `tensors.safetensors` (the saved latents and decoded tensors, `--save-tensors`)
is 173.6 MB per run.

### Phase timings, first light vs the INT8 run

| Phase | pruned (`smoke-...221709Z`) | int8 (`smoke-...222143Z`) | Note |
| --- | ---: | ---: | --- |
| `encode.tokenize` | 0.155 s | 0.167 s | 46 rows |
| `encode.load` | **12.66 s** | 13.08 s | the 27 GB INT8 Qwen3-VL text encoder, 902 tensors, 350 quantized Linears, onto xpu:0 |
| `encode.forward` | 0.70 s | 0.70 s | |
| `load.skeleton` | 0.027 s | 0.024 s | |
| `load.stream` | **33.60 s** | 18.95 s | the denoiser shard onto both cards; the int8 file is 34.0 GB against the pruned form's 40.2 GB, and there is no per-tensor LoRA merge on that path |
| `sample` | **17.68 s** | **30.80 s** | 8 transformer evaluations, ~2.2 s/step pruned |
| `decode.load_vae` | 3.30 s | 2.93 s | float32 video VAE, on the emptier card |
| `decode.video` | **11.12 s** | 11.42 s | tiled, 256x256 tiles, 64x64 minimum overlap |
| `decode.load_audio_vae` | 0.41 s | 0.49 s | |
| `decode.audio` | 2.94 s | 2.95 s | |
| `write` | 0.64 s | 0.66 s | mux to mp4, crf 16 |
| **total** | **83.2 s** | **82.2 s** | the int8 path's slower sample is paid back by its faster load |

Note the last row: end to end the two paths cost the same today, because the int8 build loads 14.6 s
faster and denoises 13.1 s slower. That equality is an artefact of a one-clip session. Anything that
amortizes the load -- a batch of prompts, a longer clip, more steps -- turns the sample column into
the only one that matters, and there the pruned path wins by 1.74x.

## Card memory: measured against the plan

The plan's per-phase budget is in
[the first-light plan](2026-09-18-first-light-plan.md#the-fix-and-the-peaks-to-expect-now)
(`--plan-memory`, computed before any card was touched). Measured figures are `max_allocated` per
phase from `receipt.json`, and the `[vram]` lines in `session.log`. The card holds 31.89 GiB usable.

| Phase | Plan xpu:0 | Plan xpu:1 | Measured xpu:0 | Measured xpu:1 | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| `encode` | 25.52 | - | **25.53** | 0.00 | **exact** |
| `load.stream` (resident after) | 19.95 | 19.89 | 18.80 | 18.75 | under, as planned |
| `sample` | 23.72 | 23.67 | **20.10** | **20.04** | **3.6 GiB under** |
| `decode.video` | 10.77 (~10.8) | 0 | 0.00 | **10.42** | **under; hypothesis confirmed** |
| `decode.audio` | 0.72 | 0 | 0.00 | 0.97 allocated after the phase | close; see below |

Three things to take from this table.

**1. The decode prediction was right, and the no-grad fix is what made it testable.** `~10.8 GiB
expected` had never been measured -- both earlier attempts OOMed before producing a number, the
second of them at 31.42 GiB because the runner was retaining autograd activations. With
`torch.set_grad_enabled(False)` in (commit `feeecf5c1`), the phase peaks at **10.42 GiB** with 21.8
GiB free on the card. The VAE loads at exactly the predicted 9.700 GiB and the decode adds 0.72 GiB
of transients on top, against the plan's ~1.07 GiB estimate. The `~10.8` row in the plan can now be
marked measured.

**2. The denoiser release works, and the VAE lands on the emptier card.** `release_denoiser()`
dropped 636 parameters/buffers and both cards returned to **0.000 GiB allocated**; the runner then
chose `xpu:1` (free 31.528 vs 31.138 GiB) and put the video VAE there. That is why the
`decode.video` row shows the peak on xpu:1 and ~0 on xpu:0 -- placement is dynamic and is recorded
in the receipt's `decode_placement`, so a future run may well pick the other card.

**3. `sample` came in 3.6 GiB under plan, and that is a real finding about attention.** Resident
shard is 18.80 GiB and the phase peaked at 20.10 GiB, so **activations cost 1.30 GiB**, not the
~4.9 GiB the plan budgeted -- of which 4.78 GiB was a *materialized* bf16 attention matrix at 4,622
packed rows. A materialized matrix of that size cannot hide inside 1.30 GiB, so **the XPU is
dispatching a memory-efficient SDPA kernel here, not building the score matrix**. That is the
question the plan flagged as the gate on the trained 544x960 canvas: if attention is never
materialized, the plan's "~80 GiB per card at 19,348 rows" upper bound does not apply and the
canvas walk is live. This is one measurement at one sequence length and it is *not* proof that the
same kernel is chosen at 4x the rows -- the 320x576 step is still the cheap way to find out, and it
is still the next thing to run.

The int8 path's own residency behaved too: 16.05 / 15.65 GiB resident as planned, peaking at
18.88 / 18.52 GiB -- 2.83 GiB of headroom consumed, which is the planned 0.484 GiB dequant transient
plus the same ~1.3 GiB of activations plus allocator slack. No sign of the float32-widening failure
mode the plan warned about (that would have shown as roughly double the residency).

Host side: **MemAvailable never went below 10.2 GiB in any MiniMax run** (lowest watchdog reading
10,391 MiB, on repeat-b), peak memory pressure `some avg10` **0**, and every watchdog log ends with
`pid ... exited on its own`. The watchdog never fired. Host peak RSS is in each receipt.

## The repeat gate: bytewise-equal

Two further runs at the same seed, same everything, rc 0 both times. `compare_receipts` compared
all four hashes from the receipts:

```
=== bytewise repeat check ========================================================
seed 42 vs 42   steps 9 vs 9
  MATCH    video_tensor_sha256  a476d723b12bfbae... / a476d723b12bfbae...
  MATCH    audio_tensor_sha256  9a66aa977ae88106... / 9a66aa977ae88106...
  MATCH    video_latents_sha256  a40845e80b76a908... / a40845e80b76a908...
  MATCH    audio_latents_sha256  22b5c54994bbe94d... / 22b5c54994bbe94d...

run A: sample 17.7 s, total 83.0 s, 16.1 s of wall per s of video
run B: sample 17.7 s, total 84.7 s, 16.4 s of wall per s of video

REPEAT GATE: bytewise-equal
```

The three `clip.mp4` files are also identical in size (857,159 bytes each). Note this was reached
**without** `--deterministic`: the default path repeats on its own on this stack, at this split, at
this canvas. That is a stronger result than the gate required and it is what licenses every A/B
below -- a hash difference between two runs is now attributable to the one setting that changed.

Full pruned-run hashes, for anyone comparing later:

| Hash | Value |
| --- | --- |
| `video_tensor_sha256` | `a476d723b12bfbae68dd069d6ebf7c99df3d09a2deefd5bbc2b710a76d73ef13` |
| `audio_tensor_sha256` | `9a66aa977ae881068129679f55213846cd13ebd2f95ae0b8730432d5691ff847` |
| `video_latents_sha256` | `a40845e80b76a9087c9dced3c7fd0a4d3833cdc0f58ad5dd63b5c43379f82405` |
| `audio_latents_sha256` | `22b5c54994bbe94d9a92b049ce7a1348df5a8d9a07e0638338e7d6163a6765bd` |

## The INT8-vs-pruned A/B

One difference, `B70_H3_DENOISER=int8`; same seed, same prompt, same canvas, same LoRA (applied at
runtime as the additive low-rank term rather than merged into the weights, because the weights are
quantized). Report: [`../data/2026-09-19-first-light/int8-vs-pruned.json`](../data/2026-09-19-first-light/int8-vs-pruned.json)
(`compare-h3-runs.py`, CPU only).

All four hashes differ, which is expected -- the two builds quantize different things. The
magnitudes:

| Tensor | max abs diff | mean abs diff | differing | dtype/shape |
| --- | ---: | ---: | ---: | --- |
| `video` (decoded pixels) | 1.0 | **0.1336** | 99.9835 % | float32 `[1, 3, 124, 256, 448]` |
| `audio` | 1.1339 | 0.1109 | 100 % | float32 `[1, 2, 165600]` |
| `latents` | 4.1700 | 0.5184 | 100 % | float32 `[1, 24, 37, 16, 28]` |
| `audio_latents` | 1.7523 | 0.2832 | 100 % | float32 `[2, 32, 207]` |

Per frame, across all 124 frames: **124/124 differ**; max abs diff per frame runs 0.956-1.000, mean
abs diff 0.0945-0.1505, differing fraction 99.91-100 %. The worst frame by max abs diff is frame 0.
Frame 62 specifically: `max|d| = 1.0`, `mean|d| = 0.1500`, 99.9927 % of pixels differ.

**Read that as "two different clips of the same scene", not as an error bar.** These are not two
approximations of one output that should have agreed: the sampler is chaotic in the weights, so any
weight change at all decorrelates the trajectory after a few steps. A mean absolute difference of
0.13 on a normalized pixel range is what "different draw from the same distribution" looks like
here; it says nothing about which draw is better.

**The qualitative note, stated as what it is.** Frame 62 of the pruned clip is a rain-slicked night
street with a neon sign, reflections and a small umbrella figure -- it matches the prompt. Frame 62
of the int8 clip is the same scene with a different composition: the umbrella figure large in the
foreground, walking away from camera toward headlights, which is arguably a closer reading of "a
lone figure with an umbrella walks away from camera". **This is one frame of one clip of one
prompt, chosen by eye. It is not a quality verdict and it does not overturn the header-level
argument** (in [the lane README](../README.md)) that the pruned build's approximation sits below the
BF16 noise floor while int8 touches every weight. A verdict needs a prompt set; see next steps.

## What it cost to get here: the five blockers, in order

Each of these stopped the lane dead, and each needed a different kind of fix. Listing them because
the next lane on this host will meet at least three of them.

| # | Blocker | What happened | The fix |
| --- | --- | --- | --- |
| 1 | **Lazy init** (2026-09-17) | `torch.xpu.reset_peak_memory_stats` raised `Invalid device argument: did you call init?` before the XPU runtime had lazily initialized -- the runner died before it touched a weight | one line: `torch.xpu.init()` before the first allocator-stats call (`a726a1a0f`) |
| 2 | **Host RAM, and an `oomd` kill** (2026-09-18 03:05 UTC) | the 27 GB text-encoder load ran under `--property=MemoryMax=4G`, beside a `JOBS=2` kernel build, on a 15 GiB host. The cgroup cap thrashed in reclaim instead of tripping; `systemd-oomd` killed the GNOME shell and then `user@1000.service`, taking every `systemd-run --user` unit with it | the `pread` tensor reader (`3dede0d4f`) so no loader ever maps the whole checkpoint -- measured host need falls to 1.663 GiB (encoder) / 0.792 GiB (denoiser); **no** cgroup memory ceiling; `mem-watchdog.sh` on `/proc/meminfo` available memory instead. [incident](../../qwen38-27b-b70/notes/2026-09-18-host-oomd-incident.md) |
| 3 | **Peer residency** (2026-09-18, session 10) | with **both** cards visible and the default allocator, every GiB placed on a card also consumed a GiB of *host* RAM (`+8,125 MiB` for an 8 GiB device allocation, measured by `xpu-host-memory-probe.py`); one card visible, it cost nothing. Not fd leakage -- making an allocation reachable from the other visible card mirrors it into host pages | `PYTORCH_ALLOC_CONF=expandable_segments:True` -- a **precondition** for any two-card run on this host, not a tuning knob. Cost drops to +54 MiB. [fault note](2026-09-18-gpu-fault-first-light.md) |
| 4 | **A GPU fault on the first cross-card copy** (2026-09-18 15:06 UTC) | sampling died 2.8 s in, at the instant hidden states first crossed xpu:0 -> xpu:1: 25 copy-engine page faults on `xe 0000:03:00.0` (`EngineClass: 3 bcs`), CAT errors, engine reset, `UR_RESULT_ERROR_DEVICE_LOST` | stage every cross-card copy through host RAM (`B70_H3_XFER=host`, now the default; bit-exact either way). Proven on 2026-09-19 14:18: same split, same canvas, all 8 steps clean. The mechanism is still **not** proven -- two earlier `bcs` faults on that card involved no P2P at all. [fault note](2026-09-18-gpu-fault-first-light.md), [DO-NOT-REPEAT row](../../qwen38-27b-b70/DO-NOT-REPEAT.md) |
| 5 | **The decode OOM was autograd, not capacity** (2026-09-19 14:41) | with the denoiser correctly released and the VAE loaded at the predicted 9.700 GiB, `decode.video` still OOMed on a 396 MiB allocation at **31.42 GiB** -- it grew ~21.7 GiB *during* the decode. Nothing in the runner ran under `no_grad`, so the ViT decoder kept every layer's activations for a backward pass that never comes, through the whole tile loop | `torch.set_grad_enabled(False)` at the top of `main()` (`feeecf5c1`). No arithmetic changes. This run is the proof: 10.42 GiB |

Two method lessons worth carrying out of this: **print residency, do not derive it** (the `[vram]`
lines added after blocker 4 turned blocker 5 into a one-run diagnosis instead of three), and **a
release that works and a phase that fits are two different claims** -- blocker 5 was hiding behind
blocker 4's fix and only appeared once that fix was proven by a printed number.

## Where the clips are

Not in Git (`*.mp4` and `*.safetensors` are ignored, and the tensors are 173.6 MB each). Under
`/mnt/fast-ai/bench-results/resume-20260919d/minimax/`:

| Path | What |
| --- | --- |
| `smoke-20260919T221709Z/clip.mp4` | **first light**, pruned BF16, 857,159 B |
| `repeat-20260919T221840Z-a/clip.mp4` | repeat gate run A, byte-identical |
| `repeat-20260919T221840Z-b/clip.mp4` | repeat gate run B, byte-identical |
| `smoke-20260919T222143Z/clip.mp4` | INT8 ConvRot, 1,041,665 B |

Each directory also holds `receipt.json` and `tensors.safetensors`. The receipts, the session log
and the comparison report are copied into the repo at
[`../data/2026-09-19-first-light/`](../data/2026-09-19-first-light/).

## Canvas ladder (22:46-22:59 UTC)

Batch window 3, **18:46-19:03 EDT (22:46-23:03 UTC)**, same boot as the two windows above, driver
`/mnt/fast-ai/bench-results/batch3-session-20260919.sh`, log `batch3-session-20260919.log`, outputs
under `/mnt/fast-ai/bench-results/minimax-h3-canvas-20260919/`. Three more runs: **576x320 pruned,
960x544 pruned, 960x544 INT8**. All rc 0, **zero `xe` fault lines**, the watchdog never fired.
Everything else was held fixed at the first-light settings -- turbo LoRA, 9 grid points (8 NFE), 124
frames, seed 42, `pread` loader, host-staged cross-card transfers, VAE tiling on.

**The headline: the trained canvas runs, on both denoisers, with room to spare.** 960x544 is the
resolution this checkpoint was trained for, and the plan's reason for doubting it -- a materialized
attention matrix at 19,348 packed rows would need ~80 GiB per card -- **does not happen**. The
pruned run peaked with 8.4 GiB still free on the tighter card. The plan's ~80 GiB bound is moot: the
XPU dispatches a memory-efficient SDPA kernel at the full length, not only at the short one.

### The five runs

Packed rows are the denoiser's sequence length: `37` latent frames x the `(H/2) x (W/2)` patch grid,
plus the same 478 audio and conditioning rows that the plan's 4,622 and 19,348 figures include.

| Run | Denoiser | Canvas | Packed rows | `sample` | s/step | `decode.video` | end to end | wall / s of video | `clip.mp4` |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `smoke-20260919T221709Z` | pruned | 448x256 | 4,622 | 17.68 s | 2.21 | 11.12 s | 83.2 s | 16.11 s | 857,159 B |
| `smoke-20260919T222143Z` | INT8 | 448x256 | 4,622 | 30.80 s | 3.85 | 11.42 s | 82.2 s | 15.90 s | 1,041,665 B |
| `smoke-20260919T224743Z` | pruned | 576x320 | 7,138 | **29.18 s** | 3.64 | **31.89 s** | 116.3 s | 22.51 s | 763,710 B |
| `smoke-20260919T224948Z` | pruned | **960x544** | 19,348 | **109.10 s** | 13.63 | **79.96 s** | **243.8 s** | 47.18 s | 3,106,978 B |
| `smoke-20260919T225400Z` | INT8 | **960x544** | 19,348 | **152.87 s** | 19.11 | 80.02 s | 273.7 s | 52.97 s | 4,891,803 B |

The first two rows are the 22:16-22:28 window, repeated here so the ladder reads in one table. Every
clip is 124 frames, 5.167 s at 24 fps, with 32 kHz stereo audio of 5.175 s. "End to end" is the sum
of the receipt's `timings_seconds`, which is the runner's own time and excludes process start-up.

### Card memory after `sample`

Read off the `[vram] after sample` lines; the card holds 31.891 GiB usable.

| Run | allocated xpu:0 / xpu:1 | reserved xpu:0 / xpu:1 | free xpu:0 / xpu:1 |
| --- | ---: | ---: | ---: |
| 448x256 pruned | 18.849 / 18.796 | 19.744 / 19.643 | 11.398 / 11.885 |
| 448x256 INT8 | 17.128 / 16.810 | 19.168 / 18.793 | 11.987 / 12.732 |
| 576x320 pruned | 18.877 / 18.823 | 20.252 / 20.090 | 10.888 / 11.438 |
| **960x544 pruned** | **19.012 / 18.955** | **22.734 / 22.395** | **8.406 / 9.133** |
| **960x544 INT8** | **17.291 / 16.969** | **26.688 / 26.137** | **4.465 / 5.388** |

Resident shard is 18.798 / 18.747 GiB (pruned) and 17.077 / 16.761 (INT8), unchanged by canvas, so
the *allocated* column moves only 0.21 GiB from the smallest canvas to the largest: at 4.2x the
sequence length, live activations grow by a fifth of a gigabyte. That is the memory-efficient
attention kernel, stated as a number.

The column that does move is **reserved**. The pruned path reserves 3.7 GiB above what it holds at
960x544; the INT8 path reserves **9.4 GiB** above what it holds, leaving only **4.5 GiB free** on
xpu:0. That is the allocator caching the large short-lived bf16 tensors the INT8 path creates and
frees on every step -- one dequantized weight and one rotated activation block at a time. It is
cache, not need, but it is the ceiling any INT8 speed lever has to work under, and it is the reason
the INT8 row is the first one that would run out of card if the canvas went further.

### How `sample` scales: linear work plus a quadratic term, and the fit is good

Three pruned points at 4,622 / 7,138 / 19,348 rows give 17.68 / 29.18 / 109.10 s. Sequence length
went up **4.19x** and `sample` went up **6.17x** -- super-linear, but nowhere near the 17.5x that a
purely quadratic cost would give. Fitting `t = a*n + b*n^2` through the **two end points only**:

* `a` = **3.256 ms per 1,000 rows** (3.256e-3 s/row) -- the per-row work: every Linear, the
  modulation, the norms.
* `b` = **1.232e-7 s/row^2** -- the attention term.

That fit predicts the untouched middle point at **29.52 s against 29.18 s measured, +1.2 %**. Two
parameters from two points landing within about one percent on a third is the model being right, not
a coincidence, and it lets the split be read off:

| Rows | Per-row part | Attention part | Attention share |
| ---: | ---: | ---: | ---: |
| 4,622 | 15.0 s | 2.6 s | 15 % |
| 7,138 | 23.2 s | 6.3 s | 21 % |
| **19,348** | **63.0 s** | **46.1 s** | **42 %** |

So at the trained canvas **attention is already 42 % of the denoising time**, and it is the part that
grows with the square. Anything above 960x544 is attention-dominated, and a chunked or
flash-style attention becomes the lever that matters there -- whereas at 448x256, where all the
earlier work was done, attention was a sixth of the cost and invisible.

### How `decode.video` scales: with the tile count, not with pixels

Decode is the fastest-growing phase in the ladder: **11.12 -> 31.89 -> 79.96 s**, a 7.2x rise for
4.55x the pixels. It is not proportional to pixels -- from 448x256 to 576x320 the pixels rise 1.61x
and the decode rises **2.87x**, which is the wrong shape for a per-pixel cost.

It does track the **number of VAE tiles**. Tiling is on in all five runs at 256x256 tiles with 64x64
minimum overlap (i.e. a 192-wide stride), which gives roughly 2, 6 and 15 tiles at the three
canvases -- ratios of 3.0 and 2.5 against measured 2.87 and 2.51. **This is a hypothesis with two
checkable ratios behind it, not a measurement:** the runner does not print the tile count, so the
first thing any decode work should do is print it. If it holds, the decode is paying overlap: every
tile re-decodes a 64-pixel border that a neighbour also decodes, and at small canvases the overlap is
a large fraction of each tile.

Either way the decode is now the **second-biggest phase and the fastest-growing one**, and it runs
**on one card in float32 while the other card sits at 0.000 GiB allocated**. That is the largest
single piece of idle hardware in the pipeline.

### Where the time goes at 960x544

The pruned run, `smoke-20260919T224948Z`, 243.78 s total, straight from the receipt's
`timings_seconds`:

| Group | Phases | Seconds | Share |
| --- | --- | ---: | ---: |
| **load** | `encode.load` 12.798 + `load.stream` 33.080 + `load.skeleton` 0.027 | **45.91** | 18.8 % |
| **sample** | `sample` 109.101 + `sample.build_pipeline` 0.001 | **109.10** | **44.8 %** |
| **decode (video)** | `decode.load_vae` 3.084 + `decode.video` 79.964 | **83.05** | **34.1 %** |
| **decode (audio)** | `decode.load_audio_vae` 0.407 + `decode.audio` 2.934 | 3.34 | 1.4 % |
| **encode (compute)** | `encode.tokenize` 0.159 + `encode.forward` 0.665 | 0.82 | 0.3 % |
| **write** | mux to mp4, crf 16 | 1.56 | 0.6 % |
| **total** | | **243.78** | 100 % |

Three sentences of reading. **Denoising is under half the run.** **Loading models is 46 seconds --
19 % -- and it is repeated in full for every single clip**, although nothing about it depends on the
prompt or the canvas. **The video decode is a third of the run on one card.** Actual generation work
that could not be avoided -- encode forward plus sample -- is 110 s of the 244.

### The INT8 path at the trained canvas

Same three-line difference as before: `B70_H3_DENOISER=int8`, LoRA applied at runtime as the additive
low-rank term, 300 runtime destinations at 2.136 GiB resident. `sample` **152.87 s against 109.10 s,
+40 %** (the gap at 448x256 was +74 %), and `decode.video` is identical at 80.02 s, as it must be --
the decode never sees the denoiser.

The overhead is **not** a constant per-step dequantization cost. In absolute terms it grew from
+13.12 s at 4,622 rows to **+43.77 s** at 19,348, which a fixed per-weight cost cannot do. Splitting
it the same way as above: about **3.5 s fixed** plus about **2.08 ms per 1,000 rows** -- so at the
trained canvas roughly **40 of the 44 extra seconds are row-proportional**, and only ~3.5 s is the
per-step weight widening.

That is exactly what `ConvRotLinear.forward` does (`run_h3_t2v.py:1107`): the weight dequant
(`qweight.to(compute)`) is one cost per call regardless of length, but the **rotation is applied to
the activations** -- `x.reshape(...) @ rotation` over every row -- and the runtime LoRA term is two
more per-row GEMMs at rank 128. Both scale with the sequence. **Caveat: this is a two-point fit with
no INT8 run at 576x320**, so the split is a prediction; an INT8 576x320 run is the one-run way to
test it, and it should be run before any INT8 speed work is scoped.

### What the clips look like

Frame 62 of **both** 960x544 clips is a convincing rainy night street: neon reflected in wet asphalt,
an umbrella figure walking away from camera. The INT8 clip shows more scene detail and a more
prominent subject. **Two frames of one prompt is not a verdict**, and the same caution as the
448x256 A/B applies -- the sampler decorrelates under any weight change, so these are two different
draws of the same scene, not two approximations of one answer. The INT8 file is also larger
(4,891,803 B against 3,106,978 B at crf 16), which usually means more high-frequency content; that
is a fact about the encoder's bitrate, not about quality.

### Host side

Nothing came close to trouble. Preflight MemAvailable 13,712 / 13,774 / 13,899 MiB; the watchdog's
lowest reading across the three runs was **9,090 MiB** (the INT8 960x544 run), peak memory pressure
`some avg10` **1**, and all three watchdogs end with `pid ... exited on its own`. Host peak RSS from
the receipts: 12.05 / 12.47 / 12.86 GB. Zero `xe` fault lines in the window.

Receipts, the batch log and the clip paths:
[`../data/2026-09-19-canvas-ladder/`](../data/2026-09-19-canvas-ladder/).

## Speed levers, none tried yet

> **Two of these have now been tried.** Batch window 4 (23:39-23:45 UTC) ran the video-decode levers
> on the cards: see [Decode experiments](#decode-experiments-2339-2345-utc) below for what they
> actually cost. Lever 1 here (decode on both cards) is exact and gains nothing; the fp16 decode that
> is not in this list at all is the one that pays. The list below is left as written.

Five, in the order the time breakdown above justifies. **None of these has been attempted**, no
number below is measured, and every one of them has to clear the same gate: either it is exact by
construction and the bytewise repeat check proves it (same seed, same everything, all four hashes
match), or it changes the arithmetic and has to be run as an A/B through `compare-h3-runs.py` with
its per-frame table beside the two clips. The repeat gate is what makes both readings possible.

**1. Decode the video on both cards, or on the idle one.** *What:* the video VAE runs on one card in
float32 while the other holds 0.000 GiB; split the tile loop, or the temporal chunks, across both --
or, cheaper to write, overlap the decode with nothing at all and simply move it to whichever card is
free. The obvious split is by tile or by temporal chunk, because tiling already decodes independent
pieces and stitches them. *Exactness:* a tile-parallel decode computes **the same tiles**, just on
two devices, so it should be **bitwise identical** and the repeat check is the whole proof -- if the
hashes match the 960x544 run above, it is exact. A temporal split is only exact if the chunk
boundaries and overlaps are unchanged, which has to be checked rather than assumed. *Expected gain:*
up to ~40 s of the 80 s decode at 960x544, i.e. **~16 % of end-to-end** -- less in practice, because
the stitch and the second card's VAE copy are not free, and the VAE would have to be resident on
both cards (2 x 9.700 GiB, which fits when the denoiser is already released).

**2. Decode in bf16/fp16 instead of float32.** *What:* the video VAE loads at 9.700 GiB of float32
weights and decodes in float32. Halving it would roughly halve the memory and should speed up the
compute-bound tiles. *The catch:* the VAE class declares `_keep_in_fp32_modules` for **everything**,
which is upstream saying this decoder is known to be unstable in half precision. *Gating:* this is a
**quality risk, not an exactness question** -- it will change every pixel, so it can only be an A/B:
same seed, same latents, `compare-h3-runs.py` per-frame max/mean absolute difference, plus frames
looked at for the specific failure modes half-precision VAEs show (banding in dark gradients, colour
drift, blown highlights). This clip is a *night* scene with dark gradients, which is the worst case
and therefore the right test. *Expected gain:* up to ~40 s of the 80 s decode and ~4.85 GiB of card;
realistically less, and **plausibly zero if the output is not acceptable**. Rank it after lever 1,
which costs no quality at all.

**3. Cache dequantized INT8 weights per block, or fuse dequant with the rotation.** *What:* the INT8
path widens each quantized weight to bf16 inside every `F.linear`, on every one of the 8 steps.
Caching the dequantized block would pay that once. *The memory budget rules out caching everything:*
the INT8 run has only **4.5 / 5.4 GiB free** at 960x544 against 32.3 GB of quantized weights, so this
is **partial caching at best** -- one block's worth at a time, or the handful of largest Linears --
and it has to be measured against a reserved figure that is already 26.7 GiB. *And the ceiling is
low:* by the split in the section above, only about **3.5 s of the 43.8 s** of INT8 overhead is the
per-step widening; the rest is row-proportional activation rotation and the runtime LoRA. So the
honest framing is that caching buys a few seconds, and the fusion is the bigger prize: **fuse the
dequant with the rotation, and fold the runtime LoRA term into the cached bf16 weight once** instead
of running two extra per-row GEMMs at rank 128 on every call. That last one attacks the
row-proportional part. *Exactness:* caching a dequantized weight is exact -- same bytes, computed
once instead of eight times -- and the repeat check proves it. Folding the LoRA into the weight is
**not** exact: it changes where the rounding happens (currently the adapter is accumulated in
float32 after the int8 GEMM), so it needs an A/B. *Expected gain:* a few seconds from caching; the
LoRA fold is unquantified and needs the 576x320 INT8 point first to size it.

**4. Keep the text encoder result and both models resident across clips -- a server, not a script.**
*What:* every run today pays **~46 s of loading**, 19 % of a 960x544 clip and 55 % of a 448x256 one,
to put a 27 GB text encoder on a card, read it once, throw it away, then stream 40 GB of denoiser
across two cards. None of that depends on the prompt. A long-lived process that holds the denoiser
resident and caches prompt embeddings (`--prompt-embeds` already exists as a path) turns the second
and every later clip into sample + decode only. *Exactness:* **exact by construction, and the
cheapest claim to prove in the whole list** -- the same weights in the same places produce the same
arithmetic, so a clip rendered from a warm server must hash identically to the same clip rendered
cold. Run the current 960x544 run, then the same seed through the server, and compare all four
hashes. *Expected gain:* **~46 s off every clip after the first**, i.e. 243.8 s -> ~198 s at
960x544 (-19 %) and 83.2 s -> ~37 s at 448x256 (-55 %). It is the largest guaranteed win here and
the only one that costs no accuracy. The cost is engineering, not arithmetic: a process that holds
~19 GiB on each card permanently, which conflicts with the FP8 service using the same cards, so it
needs the same queueing discipline the batch windows already use.

**5. The 51-step base schedule -- measure the quality before spending the time.** *What:* everything
in this note is 8 NFE with the turbo LoRA. The schedule the checkpoint was trained for is 50 NFE, and
by the fit above that is **~6.3x the sample time: roughly 680 s of denoising at 960x544**, turning a
4-minute clip into about 13 minutes. *Gating:* this is not a speed lever at all, it is the **quality
reference the other levers are judged against**, and it is only worth its cost if the turbo adapter
is actually leaving quality on the table. So: run it once at 960x544, same seed and prompt,
`compare-h3-runs.py` against the turbo clip, and look at the frames. *Expected gain:* **negative on
speed by construction.** If the two look equivalent, the turbo path is vindicated and this is never
run again; if the base is clearly better, every timing in this note is understating the real cost of
a good clip by 6x, and that changes which levers are worth building.

The ordering that falls out: **4 first** (largest, exact, no quality question), **1 second** (large,
probably exact), **5 third** (it decides what "good" means), then **2** and **3**, which are both
quality-risked and capped.

## Decode experiments (23:39-23:45 UTC)

**The pixel-conversion step is five times faster, and the way we expected to make it faster turned
out to be worth nothing.** Six GPU runs in ten minutes of card time, all rc 0, no `xe` fault lines,
watchdog never fired. The FP8 service was stopped for the window and restarted after it.

Every run decoded **the same latents** — the 960x544 pruned clip from the canvas ladder,
`smoke-20260919T224948Z` — through the new `--decode-only` path, so nothing but the decode itself
varies. The first run proves that shortcut honest: decoding the saved latents on one card in float32
reproduced **all four hashes of the original run**, so a decode-only run is a faithful stand-in for
the decode half of a full clip.

| run | decode | `decode.video` | vs the source clip |
|-----|--------|---------------:|--------------------|
| control | one card, float32 | **79.31 s** | **identical, all four hashes** |
| lever: two cards | two cards, float32 | **78.27 s** | **identical, all four hashes** |
| lever: fp16 | one card, fp16 autocast | **15.93 s** / **15.34 s** (two runs) | video differs; audio and both latents identical |
| both | two cards, fp16 | 16.81 s | video differs |

**The two-card decode is exactly right and exactly as slow.** The gate it had to clear first —
do the two B70s compute the same tile to the same bits? — **passed**: three tiles, both cards, twice,
every hash equal, with both 9.7 GiB copies of the decoder resident (9.707 GiB allocated per card) and
host memory *lower* than a normal run at 9.349 GiB. Then the full two-card decode reproduced the
source clip bytewise. And it took 78.27 s against 79.31 s: **1.01x.** The 105 tiles were split 53/52
across the cards and the wall clock did not move, which means the two worker threads never ran at the
same time. The likely cause is Python's global interpreter lock being held across each blocking GPU
operation, so two threads driving two cards just take turns; the fix would be one *process* per card,
not one thread. It is parked rather than built, because fp16 already finishes the same work in 16 s.
The reasoning, the evidence and what a process-per-card build would cost are in the
[speed plan](2026-09-19-speed-plan.md#results-window-4-2026-09-19-1939-1949-edt).

**The fp16 decode is 5.0-5.2x and it is not bit-identical.** It is the checkpoint's own documented
decode recipe — float16 autocast over float32 weights — which upstream enables only on NVIDIA cards.
It repeats exactly (the two fp16 runs are bytewise equal to each other, so this is a different
arithmetic, not a random one), and against the float32 control:

* the **audio and both sets of latents are identical**, bit for bit; only the video changes;
* **124 of 124 frames differ** and 99.83 % of pixel values differ;
* the **average** difference is 0.000115 on a 0-to-1 scale. One step of an 8-bit pixel value is
  1/255 = 0.0039, so that is **0.029 of one 8-bit level** — about a thirtieth of the smallest change
  an 8-bit image can record;
* the **worst single pixel** in the whole clip (66.4 million of them, frame 120) differs by 0.0295,
  which is **7.5 levels of 255**, about 3 % of full scale.

So: essentially every pixel moves, and it moves by far less than the file format can store. The mp4
is lossy h264 at crf 16, whose own rounding is larger than this everywhere but that one worst pixel.
What it is not is *provably* the same: the receipt hash differs from the source run and always will,
which is the whole point of having the hash.

One thing went the wrong way: fp16 uses **more** card memory, not less — 15.050 GiB peak against
11.878 GiB for float32, because autocast holds float32 masters alongside the float16 copies it makes.
It still leaves ~16.8 GiB free on a 31.9 GiB card, so nothing breaks, but the prediction that it
would *save* memory was wrong.

**What a clip costs now.** Putting the measured fp16 decode into the 960x544 run and changing nothing
else: **243.8 s becomes ~179.7 s — four minutes becomes three**, a 26 % cut, or 34.8 s of wall per
second of video against 47.2. The run's shape changes with it: decode drops from 33 % to 9 %,
**model loading rises from 20 % to 27 %** (45.9 s of reading files that depends on neither prompt nor
canvas), and **sampling rises from 45 % to 61 %**. That re-orders the lever list above: the resident /
batch-mode idea is now the biggest *exact* lever left, and the idle-card stagger is the biggest
absolute one — and it will hit the same threading wall the two-card decode just hit, so
process-per-card is on its critical path too.

**Status: fp16 is not the default.** `--vae-autocast` stays `off`. The recommendation put to the user
is to make fp16 the default and keep `off` as a flag for any run that must reproduce an existing
hash. That decision is the user's and has not been made.

Receipts, the probe JSON, the fidelity comparison and the batch log:
[`../data/2026-09-19-decode-experiments/`](../data/2026-09-19-decode-experiments/). Full analysis and
the re-ranked levers: [speed plan](2026-09-19-speed-plan.md#results-window-4-2026-09-19-1939-1949-edt).

## Next steps

In the order they are worth running.

1. ~~**Walk the canvas toward the trained 544x960, with a 320x576 step first, and read the `[vram]`
   lines.**~~ **DONE, 22:46-22:59 UTC -- and it passed.** 576x320 and then 960x544 both ran, on both
   denoisers at the top of the ladder; the plan's ~80 GiB materialized-attention bound never applied,
   live activations grew 0.21 GiB over a 4.2x rise in sequence length, and the trained canvas
   finished with 8.4 GiB free on the tighter card. See
   [Canvas ladder](#canvas-ladder-2246-2259-utc) above, and the
   [speed levers](#speed-levers-none-tried-yet) the time breakdown there produced -- which supersede
   the priority order of the items below.
2. **The 51-step base schedule against the 9-step turbo LoRA.** Everything measured so far is 8 NFE
   with the turbo adapter. The base reference is 50 NFE (`--steps 51`, `LORA=` empty), which is
   ~6.3x the sample time -- roughly 110 s of denoising at this canvas -- and it is the schedule the
   checkpoint was actually trained for. Until that runs at the same seed and prompt, we do not know
   what the turbo adapter costs in quality, and every timing in this note is a turbo timing.
3. **A small prompt set, then a real pruned-vs-INT8 comparison.** The A/B above is one prompt, one
   seed, one frame looked at by eye. A verdict needs maybe 8-12 prompts spanning motion, faces,
   text, and quiet scenes, run at 2-3 seeds each on both denoisers, with the frames put side by side.
   `compare-h3-runs.py` already produces the per-frame numbers; what is missing is the prompt list
   and a contact sheet. Worth doing before either build is called the lane's default.
4. **Decide what the INT8 path is for, given its speed.** It denoises at **30.80 s against 17.68 s**
   -- 1.74x slower, ~3.85 s/step against ~2.21 s -- because there is no fused int8 GEMM on XPU, so
   every quantized weight is widened to bfloat16 for each `F.linear`, on every one of the 8 steps.
   It buys 2.7 GiB of card residency and a 14.6 s faster load, neither of which is scarce right now
   at this canvas. If the canvas walk finds a size where the pruned form no longer fits, the int8
   path is the fallback that makes it fit; otherwise its role is the control that isolates the
   pruned AdaLN re-parameterisation, which is exactly what step 3 above uses it for.

Not urgent, but still open from the plan: the two arithmetic A/Bs (`--adaln-out-dtype fp32`,
`--te-rotation none`) and the `--denoiser-rotation none` control on the int8 path, all of which the
repeat gate now makes readable.

## Related

* [First-light plan](2026-09-18-first-light-plan.md) -- the step sequence, the preconditions and the
  memory budget these numbers are measured against.
* [Stand-up prep](2026-09-18-standup-prep.md) -- how the pipeline was built and what was assumed.
* [GPU fault, first light](2026-09-18-gpu-fault-first-light.md) -- blockers 3 and 4.
* [Lane README](../README.md) -- what the model is, and the two denoiser builds side by side.
* [Receipts](../data/2026-09-19-first-light/) -- the four `receipt.json` files, `session.log`, and
  the comparison report.
