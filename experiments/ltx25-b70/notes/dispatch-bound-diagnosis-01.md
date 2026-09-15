# The LTX clip is CPU-dispatch-bound, not GPU-bound

September14, 2026, after the user's reboot (boot `64bbd5d2`). One server,
`encoder-server-host-embedding-13` on packet12, five control clips, then a
clean stop. This note is a **diagnosis, not a speed result**: nothing here
changed the runtime and no optimization is promoted.

## Post-reboot control baseline (re-established, exact)

Four warm control clips preview in **6.312–6.450 s** (median **6.363 s**); the
cold first clip took 55.388 s including initialization. All five clips matched
their original references **bytewise on all four raw outputs** (images, video
latent, audio latent, waveform). Same 256x256, 25 frames, 24 fps, native BF16,
8+3 steps. This agrees with the pre-reboot 6.297 s median, so the reboot did not
move the baseline.

## Where the 6.36 s goes, and what the CPU is doing

Per-node client event intervals with the server process's own `utime+stime`
sampled at 50 Hz from `/proc` (read-only; no instrumentation was added):

| Node | Stage | Median wall | CPU core-s | CPU per wall |
| --- | --- | ---: | ---: | ---: |
| 344 | Sampler stage1 (8 steps, M=64) | 2.545 s | 2.875 | **1.13** |
| 364 | CLIPTextEncode (Gemma4 12B) | 1.800 s | 2.460 | **1.37** |
| 368 | Sampler stage2 (3 steps, M=256) | 1.015 s | 1.200 | **1.18** |
| 374 | VAEDecode (video) | 0.606 s | 0.690 | **1.14** |
| 358 | LTXVAudioVAEDecode | 0.176 s | 0.175 | **0.99** |

**Every GPU stage consumes at least one saturated CPU core per wall second.**
That is the central observation. It has two possible readings — Python is
issuing work too slowly, or the thread is busy-spinning inside a blocking wait
for the GPU — and they imply opposite strategies, so they were separated.

## Separating dispatch cost from GPU wait

A 200 Hz py-spy attachment over one clip (which still previewed in 6.328 s and
still matched bytewise) splits cleanly by stage:

**Sampler, 381 worker samples — spread across many issue sites, no single wait:**

| Leaf | Share |
| --- | ---: |
| `torch/nn/modules/linear.py:134` (F.linear issue) | 22.6% |
| `torch/nn/functional.py:3012` (rms_norm) | 11.0% |
| `ops.py:61` (scaled_dot_product_attention) | 7.1% |
| `eager/rope.py:40-41` (apply_rope_split_half1) | 6.6% |
| `av_model.py:216-217` (get_ada_values) | 4.4% |
| `av_model.py:67` (expand_for_computation) | 3.7% |

`rms_norm` and RoPE are tiny GPU operations; they cannot be 17.6% of GPU time.
They are 17.6% of *issue* time. This is the signature of dispatch-bound
execution: one core spread thin over hundreds of distinct operation launches.

**CLIPTextEncode, 360 worker samples — one line dominates:**

| Leaf | Share |
| --- | ---: |
| `model_management.py:1568` (`r.copy_(weight)`, blocking CPU->XPU) | **78.9%** |
| `ops.py:432` (cast_bias_weight) | 5.8% |

## Why the GEMMs are not the problem

An offline probe (no ComfyUI, no model load, synthetic BF16 weights of the
checkpoint's shapes, exclusive GPUs) measured a 536.8 GB/s device copy roofline
and these achieved rates at the real token counts:

| Layer shape | M | Time | Achieved |
| --- | ---: | ---: | ---: |
| `ff.net.0.proj` 16384x4096 | 64 | 0.246 ms | 545.1 GB/s |
| `ff.net.2` 4096x16384 | 64 | 0.234 ms | 573.5 GB/s |
| `attn.to_q` 4096x4096 | 64 | 0.059 ms | 571.2 GB/s |

**The individual linear layers already run at or above the measured copy
roofline.** There is no GEMM efficiency left to recover. Summing every linear in
one block gives roughly 1.45 ms; a block holds 773.5 MB of state, so 48 blocks
read 42.0 GB per step, about 72 ms/step at roofline. Adding the six attentions
and the elementwise work gives an estimated ~1.9 ms/block, ~91 ms/step.

Measured sampler cost is ~318 ms/step. **Roughly three quarters of sampler wall
time is operation-issue overhead, not GPU work.** The transformer is confirmed
fully resident (`loaded completely, full load: True`, 19,908 MB on XPU0 and
20,143 MB on XPU1), so no weight streaming explains the gap.

## Consequence: two levers, and one plan this retires

This retires the transformer output-column partition lead as a *speed* lever.
Splitting one FF projection across devices attacks the ~91 ms/step that is
already at roofline while adding Python work and transfers to the ~227 ms/step
that is the actual cost. Its bitwise gate is still useful and was run offline:
full-N versus two N/2 halves is **bit-identical** for `ff.net.0.proj`,
`ff.net.2` and `attn.to_q` at M=64 and M=256, and **not** bit-identical for
`audio_ff.net.0`/`audio_ff.net.2` at M=256. Recorded for future use; not a
speed path.

The two levers this diagnosis actually supports:

- **A — text encoder full residency.** The encoder is the only component not
  fully loaded: `--reserve-vram 6` leaves 24,586 MB usable on a 32,657 MB card
  for ~25,141 MB of weights, so 457-600 MB stay on CPU and are re-copied through
  blocking pageable transfers every forward. Offloaded bytes grew 457->600 MB
  across five requests while encode time stayed flat at 1.795-1.802 s, so the
  cost tracks the *number* of synchronous copies (each drains the queue), not
  the bytes. Lowering the reserve so the encoder is fully resident should remove
  the 78.9% `cast_to` occupancy. Weight values are unchanged, so outputs are
  expected bit-identical; that must still be proven by the four-tensor gate.
- **B — graph capture of the transformer step.** `torch.xpu.XPUGraph` exists in
  torch 2.14.0+xpu. Replaying a captured step issues the recorded command list
  with no Python, which is exactly the cost identified above, and it is
  bit-exact by construction: same kernels, same order, same buffers. Not yet
  validated on this hardware; that is the next offline gate.

Neither lever changes the checkpoint, precision, resolution, frame count,
sampler or step schedule.

## Limitations

Client node intervals are approximate wall time, not synchronized kernel
timings. py-spy stack occupancy is not kernel duration and nonblocking sampling
drops frames. The GEMM probe used synthetic weights of the checkpoint's shapes,
not loaded model weights, and measured isolated calls rather than in-model
sequences. Four warm clips is a small sample. No speed claim is made here.

Evidence: [`data/dispatch-bound-diagnosis-01.json`](../data/dispatch-bound-diagnosis-01.json).
