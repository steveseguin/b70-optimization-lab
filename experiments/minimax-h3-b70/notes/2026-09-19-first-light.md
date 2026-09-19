# MiniMax-H3 first light: the pipeline renders, and it repeats bit for bit (2026-09-19)

Date: 2026-09-19, batch window 2, **18:16-18:28 EDT (22:16-22:28 UTC)**. Host
`steve-TURIND8-2L2T`, two B70s, same boot as the 17:20 EDT two-card service start (no reboot in
between). Driver script `/mnt/fast-ai/bench-results/batch2-session-20260919.sh`, log
`batch2-session-20260919.log`, session root `/mnt/fast-ai/bench-results/resume-20260919d`
(`session.log` there, runs under `minimax/`). **Zero `xe` fault lines all evening.**

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

## Next steps

In the order they are worth running.

1. **Walk the canvas toward the trained 544x960, with a 320x576 step first, and read the `[vram]`
   lines.** This is the question the `sample` measurement above half-answered. The memory plan warns
   that at 544x960x124 the packed sequence goes from 4,622 rows to 19,348 and a *materialized*
   attention matrix there would be ~80 GiB per card -- far over. Today's run says nothing is
   materialized at 4,622 rows (1.30 GiB of activations against a 4.78 GiB materialized-matrix
   budget), which is encouraging and is not the same as an answer at 4x the length; kernel selection
   can change with shape. Run 320x576 first, read `[vram] before sample` / `after sample`, and let
   that number decide whether 544x960 is attempted or whether attention has to be chunked first. The
   decode is not the worry at any of these sizes: tiling holds the tile fixed and the plan puts
   544x960 at 11.34 GiB.
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
