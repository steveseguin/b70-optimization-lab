# MiniMax-H3 on two B70s: where the time goes, and what to do about it

2026-09-19, design memo. Read-only: nothing here was run on a card, and no GPU, docker or systemd
was touched. Every number is either read out of the canvas receipts and logs in
`/mnt/fast-ai/bench-results/minimax-h3-canvas-20260919/` or is arithmetic from shapes, and which one
it is is stated each time.

Baseline, 960x544 / 124 frames / turbo LoRA / 9 sigma grid points = 8 NFE
(`pruned-960x544/smoke-20260919T224948Z/receipt.json`, `int8-960x544/smoke-20260919T225400Z/receipt.json`):

| phase            | pruned BF16 | int8 ConvRot |
|------------------|------------:|-------------:|
| encode.load      |      12.80 s |      12.77 s |
| encode.forward   |       0.67 s |       0.70 s |
| load.stream      |      33.08 s |      19.08 s |
| sample (8 NFE)   |     109.10 s |     152.87 s |
| decode.load_vae  |       3.08 s |       3.07 s |
| decode.video     |      79.96 s |      80.02 s |
| decode.audio     |       2.93 s |       2.98 s |
| write            |       1.56 s |       1.53 s |
| **total**        |  **243.8 s** |  **273.5 s** |

Two facts frame everything below. `decode.video` is 80.0 s on both paths to within 0.07 % — it is
downstream of the denoiser and does not care which ran. And the 5.2 s clip costs 47 s of wall per
second of video (`seconds_per_second_of_video: 47.183`), of which 49 s per run is pure loading.

## Ranking (expected gain x confidence / effort)

> **Superseded by measurement.** This was the pre-flight ranking, written before any of it ran. Both
> experiments and both built levers went to the cards in batch window 4 (2026-09-19 19:39-19:49
> EDT): lever 1 pays **5.0-5.2x** and lever 2 pays **nothing**, for a reason this table did not
> anticipate. The measured numbers and the re-ranking are in
> [Results, window 4](#results-window-4-2026-09-19-1939-1949-edt); read that first and this table as
> the prediction it is being scored against.

| # | lever | gain / clip | bit-identical | confidence | effort |
|---|-------|------------:|---------------|-----------|--------|
| 1 | fp16 autocast in `decode.video` (the checkpoint's own documented recipe) | ~30-45 s | **no** — A/B required | medium | ~2 lines |
| 2 | two-card tiled VAE decode | ~35 s | **yes** | high | ~150 lines |
| 3 | overlap loads with idle cards (card-1 shard during `encode`, VAE copy B during copy A's first tiles) | ~12-15 s | yes | medium-high | ~40 lines |
| 4 | batch mode: N prompts in one process | ~49 s per extra clip | yes | high | ~120 lines |
| 5 | two clips staggered through the block-24 pipeline | up to ~54 s amortised | yes | medium | high, pruned-only |
| 6 | share the qkv activation rotation (int8 only) | ~2-5 s of 153 s | yes | medium | ~15 lines |
| 7 | fast Hadamard rotation (int8 only) | up to ~25 s of 153 s | no | low-medium | high |
| 8 | cache dequantised BF16 weights (int8 only) | — | yes | — | infeasible, see §2 |

Levers 1-4 are all in the decode/load half, where the cheap seconds are. The sample phase already
runs near the card's limit (§4); its only real lever is the idle half — lever 5, the dearest build.

## 1. The video VAE decode: 80 s

### 1.1 What `decode` actually does

`AutoencoderKLMiniMaxH3.decode` (autoencoder_kl_minimax_h3.py:873-894) casts the latents to the
decoder's parameter dtype and calls `_decode`. Every module is pinned float32 by
`_keep_in_fp32_modules` (L532), so `torch_dtype=torch.float16` narrows nothing, the weights are
9.700 GiB (`[vram] after decode.load_vae`), and **the whole ViT decoder runs in float32**.

`_decode` (L793-842) chunks time: with `clip_length=17`, `token_drop=3`, temporal ratio 4 ->
`tokens_chunk_size = 5`, `token_overlap = 2`, `frame_pre_padding = 3`, `frame_overlap = 5`
(L596-599). For 37 latent frames: `pad_tokens = 0`, **7 temporal chunks**, each decoding `5 + 2 = 7`
latent frames and cross-fading 5 pixel frames against its predecessor with `_blend` (L668-686).

`_decode_clip` (L735-763) tiles space. Tiling is **on by default** (L608, and the class docstring at
L520-522: the released frames are the blended-tile ones). `_split_tiles` (L645-666) lays 256-pixel
tiles with a >= 64 pixel overlap and pushes all slack into the overlaps in 16-pixel steps: at
960x544, rows `[0, 144, 288]` (overlaps 112, 112) and columns `[0, 176, 352, 528, 704]` (overlaps
80 x 4) — **3 x 5 = 15 tiles** of 256x256. Each goes through `post_quant_conv` then the 36-layer
ViT, and `_stitch_tiles` (L688-708) blends them in a fixed row-major order.

The ViT decoder (L398-498) makes one token per latent voxel, appends 4 register tokens plus a zero
token, runs **full self-attention** with 3-axis RoPE, and expands each token into a 4x16x16 pixel
block. Attention goes through `dispatch_attention_fn` with `backend=None` (L331-338) -> the `native`
default (`utils/constants.py:45`) -> `F.scaled_dot_product_attention` (attention_dispatch.py:3684).

### 1.2 Where the 80 s goes: tiles x per-tile cost, and it is linear

Tokens per tile: `(5+2) * 16 * 16 + 4 + 1 = 1797`. Calls per decode: `7 chunks x 15 tiles = 105`.

    960x544:  105 tile-decodes / 79.964 s  ->  0.7616 s per tile
    576x320:   42 tile-decodes / 31.893 s  ->  0.7594 s per tile   (2 x 3 tiles x 7 chunks)

0.3 % apart across a canvas that differs by 2.9x: the decode is exactly `tiles x per-tile cost`,
the per-tile cost is fixed by the tile geometry, and the canvas only changes the tile count. That is
what makes the two-card estimate below a prediction rather than a hope.

Per tile, per layer, at d = 2048 and S = 1797: 1.338e11 MACs; x36 layers = **9.64 TFLOP per tile**
in float32, i.e. 12.6 TFLOP/s fp32 on one card. Split: FFN 67 %, projections 23 %, attention 10 % —
**the decode is GEMM-bound, not attention-bound**, which is why fp16 (lever 1) is the biggest single
number here.

The fp32 score matrix is `32 x 1797^2 x 4 B = 394.2 MiB` per layer — the 396.00 MiB the 2026-09-19
OOM traceback asked for inside `_native_attention` (run_h3_t2v.py:2932-2937). So SDPA takes the
**math path** in fp32 and materialises the scores. Tiling caps that transient: a 256x256 tile has
1797 tokens at any canvas, which is why `decode.video` peaks at the same 12.754 GiB at 256x448 and
at 960x544.

Structural waste, for the record: the 15 tiles cover 983,040 px against a 522,240 px frame
(**1.88x**) and each chunk decodes 7 latent frames to contribute 5 (**1.4x**) — ~2.6x the work of a
single untiled pass. Recovering it changes the tile geometry and so the pixels: a future A/B.

### 1.3 A two-card decode that is bit-identical

Both cards are empty when decode starts (`[vram] after denoiser release`: 31.136 / 31.528 GiB free)
and the VAE is 9.700 GiB, so two replicas fit with ~20 GiB to spare each.

1. **Replicate the VAE.** Load copy A with `from_pretrained` as today; build copy B by walking copy
   A's parameters and buffers through `cross_card()` (run_h3_t2v.py:1467-1496) into a second
   `AutoencoderKLMiniMaxH3` skeleton built on `meta`. *Not* a second `from_pretrained`: that maps
   the 9.7 GB checkpoint again, and host VmHWM is already 12.467 GiB on a 15 GiB host (the watchdog
   logged MemAvailable down to 9,755 MiB). The card-to-card copy stages one tensor at a time and
   gives copy B **byte-identical weights by construction**.
2. **Dispatch tiles.** Replace `_decode_clip`'s double loop: enumerate tiles in the existing
   row-major order, hand tile `k` to card `k % 2`, drive the two cards from two Python threads
   (torch releases the GIL, each thread owns a queue), join.
3. **Gather.** Bring every card-B tile back to card A with `cross_card()` — host-staged, **no P2P**,
   per the 2026-09-18 copy-engine fault (run_h3_t2v.py:1440-1461).
4. **Blend unchanged.** Rebuild the original `rows` list-of-lists positionally and call the stock
   `_stitch_tiles` on card A: same arithmetic, same order, same device as today.

Flattening across chunks gives 105 units split 53/52 (1.98x ideal); staying inside a chunk gives 8/7
of 15 (1.875x). The 105-way split is worth the extra plumbing.

### 1.4 Why this is bit-identical, and what would break it

Identical because: (a) each tile's computation reads only its own latent slice and the weights —
`_decode_clip` decodes every tile before any blending, so there is no tile-to-tile data flow
(L751-761); (b) the weights on card B are the same bytes as on card A; (c) the blend consumes the
tiles in the original order on the original device, so the only float op whose operand order could
have changed did not change; (d) every crossing is a copy, and a copy does not change values
(run_h3_t2v.py:1470-1472).

What could break it, in order of likelihood:

- **Kernel selection differing between cards.** Same model, same driver, same shapes, so the same
  oneDNN/SYCL kernel should be picked — but "should" is not a receipt. A GEMM picking a different
  split-k or M-class on one card changes the reduction order and flips bits; this lane has already
  seen exactly that in the FP8 work. **E1 measures this before anything is built.**
- **Per-device allocator state** changing a kernel's tiling choice. Unlikely; the same probe catches
  it if it recurs across repeats.
- **A shared module object.** Two threads must not touch one `nn.Module`: two full replicas, and
  `with torch.xpu.device(dev)` per thread, no `set_device` races.
- **Completion-order blending.** Cannot happen if the gather rebuilds the tile list positionally.
  Write it positionally.

### 1.5 Expected speedup and its ceiling

Ideal 105/53 = 1.98x on the kernels: 79.96 s -> 40.4 s. Overheads:

- **Transfers.** 52 tiles come back at `3 x 28 x 256 x 256 x 4 B = 22.0 MB` each -> 1.14 GB
  device->host->device; at a conservative 5 GB/s per direction, ~0.46 s (~1 %).
- **Second VAE load.** ~3.1-3.5 s (`decode.load_vae` measures 3.08 s). It **cannot** be hidden under
  `sample`: peak allocated there is 23.679 / 23.400 GiB (pruned) and 26.483 / 25.920 GiB (int8),
  leaving 4.5-8.4 GiB free against 9.7 GiB needed. That question is settled — no. It **can** be
  hidden under decode itself: start card A's first tiles while a second thread builds copy B.
- **Blend and tail.** Unchanged, already inside the 80 s.

Realistic: **80 s -> 44-46 s naive, 41-43 s with the load overlapped**, ~35 s off a 244 s run
(14 %). Ceiling is 2x minus transfers, ~40.5 s; the last seconds are not worth chasing.

## 2. The INT8 path: +43.8 s on sample (+40 %)

`ConvRotLinear.forward` (run_h3_t2v.py:1107-1141) per call: cast the activation; **keep an unrotated
copy** for the LoRA; reshape into groups of `group_size` and multiply by `R`;
`F.linear(x, self.qweight.to(compute))` — which **materialises a bf16 copy of the whole int8 weight
every call**; apply the per-row scale in float32 after accumulation; add `scale * B(Ax)`; add bias.
Per block the quantised Linears are qkv 115.6 MB, out_proj 38.5 MB, fc1 154.1 MB, fc2 77.1 MB and
**adaln_proj 260.1 MB** = 645.5 MB of int8.

Three costs, sized from shapes (not profiled):

- **Dequant traffic**: 645 MB read + 1.29 GB written per block per forward = ~97 GB per forward.
- **Rotation**: 2.13e11 MACs per block = 21.3 TFLOP per forward (1.7 % of the stack's FLOPs) but in
  a K=256, N=256 grouped shape no GPU runs near peak, over 3.3 GB of activation traffic per block.
- **Runtime LoRA**: 4.43e11 MACs per block = 44.3 TFLOP per forward, **3.5 %** of the stack, and
  pure overhead against the pruned path where the same adapter is merged at load
  (run_h3_t2v.py:2048-2064). Of the +43.8 s this is the one term that is not quantisation at all.

Worst ratio in the file: `adaln_proj.linear` dequantises 260 MB of int8 into 520 MB of bf16 **to run
a 3-row GEMM** (`temb` has one row per distinct timestep) — 40 % of the per-block dequant traffic
for 0.06 % of the per-block arithmetic.

**(a) Cache the dequantised BF16 weight per Linear.** Bit-identical: **yes** — int8 up to +-127 is
exact in bf16, the conversion is deterministic, and `F.linear` sees the identical operand. Memory:
**1.202 GiB per block**, 60.1 GiB for all 50, against 4.465 / 5.388 GiB free at the end of sample
(`[vram] after sample`, int8). That is **3 blocks of 50**. Infeasible.

**(b) Cache only the largest GEMMs.** The largest weight is the one with the least work
(`adaln_proj`, 520 MB bf16): 4.5 GiB buys 8 blocks of 50, ~16 % of the adaln dequant traffic, maybe
1-2 s of 153. Bit-identical, not worth the residency risk.
**(c) Fast Hadamard via the Kronecker structure.** `convrot_rotation` (run_h3_t2v.py:1146-1180)
already proves `R256 = A^(x)4` with `A` the symmetric order-4 Hadamard, verified against real
weights. Four butterfly stages cost 16 ops/element instead of 256 — a **16x** cut, turning a bad
GEMM shape into a bandwidth-bound pass. Bit-identical: **no** — the dense matmul accumulates 256
terms in one fp32 accumulator and rounds once, the butterfly rounds at every stage. Gain is bounded
by the rotation's share of the +43.8 s (plausibly 10-25 s); the risk is a different error profile in
every quantised Linear, to be measured with `compare-h3-runs.py`, not asserted.

**(d) Pre-rotate weights into BF16 at load.** This is (a) renamed, and worse than it sounds:
dequantising gives `W R` at 60.1 GiB — *larger* than the 40.2 GB pruned BF16 file, because the int8
checkpoint carries the unpruned 96768x2688 AdaLN branch. Un-rotating to `W` is a second load-time
matmul *and* changes the arithmetic (`x W^T` instead of `(xR)(WR)^T`). Infeasible and non-identical.

**(e) The one free win: share the qkv rotation.** `to_q`, `to_k`, `to_v` are three separate
`ConvRotLinear`s (run_h3_t2v.py:419-425) each computing `x @ R` on the *same* activation with the
*same* rotation. Memoising that per (tensor, group size) for the life of a block's forward is
**bit-identical by construction** — same op, same operands — and removes 2 of the 3 widest rotations
per block: 5.3e10 MACs and ~830 MB of activation traffic per block per forward.

**Honest bottom line for §2:** the int8 path's +43.8 s cannot be bought back within the memory this
host has. If the run needs speed, the pruned BF16 denoiser is 43.8 s cheaper and is the control;
the int8 path is for the fidelity question, not the speed question.

## 3. A persistent server, and what it can actually save

The encoder is 25.278 GiB on card 0 (`[vram] after encode.forward`) and the denoiser's primary
shard is 18.798 GiB. 25.3 + 18.8 = 44.1 > 31.89. **They cannot co-reside**, so "keep the encoder
warm" buys only its own load, and only if nothing else needs that card. The saving is the *reloads*,
not the residency.

Per-run fixed costs: `encode.load` 12.80 + `load.stream` 33.08 + `decode.load_vae` 3.08 +
`decode.load_audio_vae` 0.41 = **49.4 s**, 20 % of a 243.8 s run. Per-clip variable costs:
`encode.forward` 0.67 + `sample` 109.10 + `decode.video` 79.96 + `decode.audio` 2.93 + `write`
1.56 = 194.2 s.

Minimal batch mode — `--prompts-file` with N prompts, one process:

    A  load encoder (12.8 s), encode all N prompts (0.67 s each), free encoder
    B  load the denoiser once (33.1 s), sample all N clips, release
    C  load the video VAE once (3.1 s), decode all N videos, release; D  audio VAE (0.4 s), same
    E  write each mp4 + receipt as soon as its clip is decoded (see the host-RAM note)

Host RAM, the binding constraint at 15 GiB: prompt embeds [1, 46, 5120] bf16 = 0.47 MB per clip,
video latents [1, 24, 37, 34, 60] fp32 = 7.25 MB, audio latents [2, 32, 207] fp32 = 0.05 MB. **20
clips is 155 MB** — latents are free, they are not the constraint. The constraint is phase C's
*output*: one decoded clip is `3 x 124 x 544 x 960 x 4` = **777 MB** on the host, so phase C must
write and free each clip before decoding the next (interleave E into C) and never accumulate;
`--save-tensors` makes it worse. VmHWM is already 12.467 GiB with MemAvailable down to 9,755 MiB, so
batch mode must not raise the high-water mark at all — a `[mem]` line per clip boundary
(`B70_H3_LOG_MEM=1`, run_h3_t2v.py:1325) is the gate.

Saving: **49.4 s per additional clip**, ~20 %, ~25 % if lever 3 lands. Bit-identical: phase order
touches no arithmetic and each clip keeps its own `torch.Generator` seeded the same way
(run_h3_t2v.py:3288) — the repeat gate must confirm that clip-by-clip against the single-clip
receipts.

## 4. The sample phase: 109 s

Packed sequence at 960x544: 18,870 video rows (37 latent frames x 17 x 30 patches) + 414 audio rows
(207 per channel x 2) + 46 text rows = **19,330** (before_denoise.py:309-312; the receipt's
`video_latents_shape` and `audio_latents_shape` give the first two, `prompt_tokens: 46` the third).

Per layer, per forward, from `MiniMaxH3TransformerBlock` (transformer_minimax_h3.py:319-373) at
hidden 5376, inner 7168, ffn 14336:

| term | MACs | share |
|------|-----:|------:|
| qkv projections | 2.235e12 | 17.5 % |
| attention scores + AV (S^2) | 5.357e12 | 41.8 % |
| out projection | 0.745e12 |  5.8 % |
| SwiGLU FFN | 4.469e12 | 34.9 % |
| **total** | **1.281e13** | |

**Attention family 65 %, MLP 35 %.** x50 layers = 1.28 PFLOP per forward; x8 NFE = 10.2 PFLOP in
109.1 s = **93.9 TFLOP/s aggregate bf16**.

Cross-check that this model of the phase is right: at 576x320 the same formula gives 3.68x fewer
FLOPs and the measured ratio is 109.101/29.176 = **3.74x**. The sample phase tracks its FLOP count
to 1.6 % across a 2.9x canvas change — it is compute-bound with no meaningful fixed overhead, and
there is no kernel-efficiency lever hiding in it.

**Which SDPA backend.** `dispatch_attention_fn` defaults to `native` -> `F.scaled_dot_product_attention`
(attention_dispatch.py:391-405, 3684-3722; `utils/constants.py:45`). A materialised bf16 score
tensor at 56 heads x 19,330^2 would be **41.8 GB**; measured peak activations are 4.88 GiB pruned
(23.679 max allocated minus 18.798 resident) and 1.31 GiB at 576x320. So the XPU takes a **fused /
memory-efficient SDPA kernel** here, not the math path — the opposite of the VAE decode (§1.2), and
the difference is almost certainly dtype (bf16 vs fp32). Another reason to expect lever 1 to pay
twice: fp16 GEMMs *and* a fused attention kernel.

**The idle half.** The split is at block 24 (`split_plan.split_index: 24`), chosen by bytes
(run_h3_t2v.py:920-928), and `cross_card()` synchronises at the boundary, so the halves are
**strictly serial by construction**: card 0 busy ~48 % of the phase, card 1 ~52 %. **~109
card-seconds of idle per clip**, one entire card-run. Note what 93.9 TFLOP/s then implies: each card
sustains ~94 TFLOP/s *while busy*. Whatever the B70's bf16 peak is, the conclusion holds — the
kernels are not the problem, the idle half is.

**What can use it without P2P.** Tensor and context parallelism are out: both need per-layer
collectives, and every crossing here is host-staged (2 x 208 MB for a [1, 19330, 5376] bf16 hidden
state, ~70 ms) — 50 of those per forward would eat the gain. What fits the existing boundary is
**staggering two clips**: clip A on blocks 0-23 while clip B is on 24-49, hand off, swap. Both clips
already exist in batch mode (§3) and the hand-off is the same tensor on the same route, just twice
as often. Cost is two live activation sets: pruned, 12.519 / 12.849 GiB free before sample against
4.88 GiB per clip — fits with ~2.7 GiB spare; int8, 14.228 / 14.899 GiB free against 9.4 GiB per
clip — **does not fit**, so lever 5 is pruned-only. Ideal: 2 clips in ~113 s of sample instead of
218 s, ~54 s amortised per clip. Risks: the synchronous `cross_card()` serialises the two threads
unless one card's copy is staged against the other's compute; and the repeat gate must hold per
clip, which it should, since neither clip's arithmetic sees the other.

## 5. The first two experiments

Both are **measurements**, not builds: under an hour of card time, and they decide the two largest
levers.

### E1 — cross-card tile identity probe (gates lever 2 before a line of it is written)

Load the video VAE on **both** cards (copy B built by `cross_card()` from copy A, §1.3 step 1). Take
the 960x544 latents from `pruned-960x544/smoke-20260919T224948Z/tensors.safetensors` and run
`post_quant_conv` + `decoder` on **the same 3 tiles** (first, middle, last of chunk 0) on each card.

Gates, all four must pass:

1. **Identity**: `sha256_tensor()` of each tile equal across cards, all 3 tiles. *One mismatch kills
   the bit-identical framing of lever 2* — the fallback is to call the two-card decode an
   arithmetic change and put it through `compare-h3-runs.py`, a much weaker proposition.
2. **Repeatability**: each card's own tile hash equal across two consecutive runs.
3. **Memory**: `[vram]` <= 12.5 GiB allocated per card with both replicas up.
4. **Host**: VmHWM no more than 0.5 GiB above today's 12.467 GiB while copy B is built — this is
   what proves the cross-card build beats a second `from_pretrained`.

If all four pass, build lever 2 and gate the finished decode on
`video_tensor_sha256 == ac730503b4380001566532ca6e03fb9752250f44488b0dee7c9baff244a35280` and
`audio_tensor_sha256 == 73c26c2a08d4725193f81f36ef6255437f2dbc3f48dc044275e7d17633beea5d` —
exact equality with the single-card pruned receipt, nothing weaker.

### E2 — fp16 autocast decode A/B (gates lever 1)

The VAE's own docstring names the recipe: "the verified decode recipe is float16 *autocast over
float32 weights*" (autoencoder_kl_minimax_h3.py:529-530). Upstream implements it and then disables
it off CUDA — `torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda")`
(`modular_pipelines/minimax_h3/decoders.py:187`). So our full-fp32 XPU decode matches upstream's XPU
behaviour, and switching it on is a deliberate documented deviation, not a bug fix. Wrap
run_h3_t2v.py:3329-3336 in that autocast with `enabled=True` and rerun the identical command line.

Gates:

1. **Time**: `decode.video`. Expect 35-50 s. Above 70 s means autocast is not reaching the GEMMs;
   stop and profile.
2. **Repeat**: run it twice; the four receipt hashes must match between the two autocast runs. *If
   they do not, fp16 autocast on XPU is not deterministic here and the lever is dead*, whatever its
   speed — the repeat gate is not negotiable.
3. **Fidelity**: `scripts/compare-h3-runs.py <autocast-run> pruned-960x544/smoke-20260919T224948Z`;
   record per-frame max and mean absolute difference and the differing fraction. State the numbers,
   do not characterise them — whether that error is acceptable is the user's call.
4. **Memory**: `[vram] after decode.video` under the fp32 path's 12.754 GiB (the 394 MiB score
   matrix should halve to ~197 MiB).

E1 and E2 are independent and compose: if both pass, decode is ~20-25 s instead of 80 s and the
clip ~185 s instead of 244 s, before anything else is rebuilt.

## 6. What was built (2026-09-19, later the same day)

Levers 1, 2 and 6 and both experiments are now code, all of them OFF by default so the
bytewise-gated path of the canvas runs is unchanged. Nothing below had been run on a card when it was
written: the FP8 service held both B70s, so everything here was validated on CPU. **It has since run
— see [Results, window 4](#results-window-4-2026-09-19-1939-1949-edt).** The GPU session is written out,
step by step and gate by gate, in `scripts/decode-experiments-session.sh`; it assumes the service is
already stopped and never touches it.

### The flags

| flag | default | what it does |
|------|---------|--------------|
| `--vae-decode {single,two-card}` (env `B70_H3_VAE_DECODE`) | `single` | lever 2. `single` is the old `vae.decode` call, untouched |
| `--vae-autocast {off,fp16,bf16}` | `off` | lever 1 / E2. Upstream's `decoders.py` autocast with `enabled=True` |
| `--decode-only --latents-from PATH` | off | decode a previous run's saved latents: ~1.5 min instead of ~4 |
| `--probe-tile-identity N --latents-from PATH` | off | E1. Writes `probe.json`, exits nonzero on a failed gate |
| `--int8-share-rotation` / `--no-int8-share-rotation` | **ON** | lever 6, on because the CPU test proves it exact |

`smoke_h3.sh` gains two modes with the same preflight and the same watchdog as every other GPU
mode: `probe-tiles` and `decode-only` (env `LATENTS_FROM`, `VAE_DECODE`, `VAE_AUTOCAST`,
`PROBE_TILES`, `RUN_NAME`).

### How lever 2 avoids editing the diffusers checkout

`decode_video_two_card()` (run_h3_t2v.py) reimplements the *loops* of `_decode` and `_decode_clip`
and calls the VAE's own methods for everything that does arithmetic: **`vae._split_tiles`**,
**`vae.post_quant_conv`**, **`vae.decoder`**, **`vae._stitch_tiles`** and **`vae._blend`**. Copy B
is built by `replicate_video_vae()`, which walks copy A's parameters and buffers (including the
non-persistent `rope.inv_freq`) through `cross_card()` into a meta-device skeleton -- no second
`from_pretrained`, so host VmHWM sees one tensor at a time.

Three details the §1.3 sketch did not have, all of which matter:

1. **The whole latent is staged to card B once (~7 MB) and sliced there**, rather than sliced on A
   and shipped. A shipped slice arrives *contiguous* while the single-card path hands its
   `post_quant_conv` a *strided view*, and a conv may pick a different kernel for the two. Staging
   the latent gives both cards a view with identical shape, strides and storage offset.
2. **The flattened 105-way split holds every decoded tile until its chunk is stitched** -- 2.3 GiB
   on the blending card at 960x544, on top of 9.7 GiB of weights. Tiles are dropped chunk by chunk
   as they are blended.
3. **The diffusers source is hashed at start-up.** `DIFFUSERS_VAE_SOURCE_SHA256` =
   `4c3c9745ee27d16ff343c4998244bad41cd8f4213f0029cf7ce11ebb6d72ca1b`. If upstream's file changes,
   the two-card path refuses to run and says so; the hash is in the receipt of every run that used
   it, and in `probe.json`.

### How each gate is evaluated

* **E1 (`smoke_h3.sh probe-tiles`)** writes `probe.json` with per-tile sha256 per card per pass.
  `gates.identity_across_cards` is gate 1, `gates.repeatable_per_card` is gate 2, `gates.vram` is
  gate 3 (<= 12.5 GiB allocated per card with both replicas up) and `gates.host_peak_rss_bytes` is
  gate 4 (no more than ~0.5 GiB above the 12.467 GiB of a normal run). The run exits nonzero if 1
  or 2 fails, and the session script stops there: a mismatch means lever 2 cannot be *called*
  bit-identical, whatever it measures.
* **Lever 2** is gated on exact equality with the single-card decode of the *same latents*. A
  `--decode-only` receipt carries `decode_only.source_hashes`, the runner logs MATCH/DIFFERS per
  hash at the end of the run, and `compare-h3-runs.py` prints the same comparison for either side
  of a pair. The control step (`single` + `off`) must reproduce the source run first; if it does
  not, `--decode-only` itself is wrong and no later number means anything.
* **E2 (`--vae-autocast fp16`)** is gated on its own repeat first -- two fp16 runs, four hashes,
  bytewise equal or the lever is dead -- then on `timings_seconds["decode.video"]`, then on
  `compare-h3-runs.py` against the fp32 control for per-frame max/mean absolute difference and the
  differing fraction. Those are numbers to report, not a verdict to reach.
* **Lever 6** is gated on CPU, in `test_convrot_linear.py` section 6: the shared and unshared paths
  are compared bitwise on a synthetic q/k/v block, and the cache statistics confirm that q/k/v hit
  (2 hits, 2 misses across four Linears) while an equal-but-distinct activation misses. It passes,
  which is why the flag defaults ON. The receipt records the flag and the hit/miss counts.

### The CPU tests

`scripts/test_vae_tile_loop.py` (new, wired into `smoke_h3.sh dry`) extracts `_split_tiles`,
`_blend`, `_stitch_tiles`, `_decode_clip` and `_decode` from the *installed diffusers source file*
with `ast`, binds them to a stub autoencoder with the real geometry, and compares upstream's
`_decode` against `decode_video_two_card` on the same latents. It checks the tile grid and the
blend extents, the per-tile decoder inputs one for one in order (shape, strides, storage offset and
bytes), and the decoded clip. All three cases -- two cards, one card, and a latent length that
forces `pad_tokens > 0` -- come out **bitwise equal**, so the reimplementation is the loop upstream
runs, on CPU. What CPU cannot answer is whether the two *cards* agree: that is E1, and only E1.

### What is not exact, and what is not built

* **fp16 autocast is not bit-identical and never will be.** It is a deliberate documented deviation
  (the checkpoint's own recipe, which upstream enables only on CUDA), and it stays off by default.
* **The two-card decode is *intended* to be exact and is unproven on hardware.** Everything under
  this lane's control is identical by construction -- same weights, same tile inputs down to the
  strides, same blend order on the same card -- but whether the two B70s pick the same GEMM kernel
  is a measurement, and it is E1.
* **Levers 3, 4, 5 and 7 are not built.** Overlapping copy B's build with card A's first tiles
  (lever 3) is a thread-ordering change to `decode_video_two_card` once E1 has passed; batch mode
  and the staggered pipeline are untouched.

## Results, window 4 (2026-09-19 19:39-19:49 EDT)

Everything in §5 and §6 ran, in one batch window, on the same latents. The FP8 service was stopped
for it and restarted after. Source of every number below: the session transcript and the
`receipt.json`, `probe.json` and `vs-control.json` copied beside it in
[`data/2026-09-19-decode-experiments/`](../data/2026-09-19-decode-experiments/). All runs are
`--decode-only` against
`pruned-960x544/smoke-20260919T224948Z/tensors.safetensors`, so the latents are literally the same
bytes in every row and only the decode differs.

### The table

| run | `--vae-decode` | `--vae-autocast` | `decode.video` | vs source video hash | speedup |
|-----|----------------|------------------|---------------:|----------------------|--------:|
| source run (for reference) | single | off | 79.96 s | (the control) | 1.00x |
| `control-single-off-…233947Z` | single | off | **79.31 s** | **identical** | 1.01x |
| `two-card-off-…233947Z` | two-card | off | **78.27 s** | **identical** | 1.02x |
| `fp16-a-…233947Z` | single | fp16 | **15.93 s** | differs | 5.02x |
| `fp16-b-…233947Z` | single | fp16 | **15.34 s** | differs | 5.21x |
| `two-card-fp16-…233947Z` | two-card | fp16 | 16.81 s | differs | 4.76x |

Peak card memory during `decode.video` (max allocated, from each receipt's `peak_memory`):

| run | xpu:0 | xpu:1 |
|-----|------:|------:|
| single / off | — | 11.878 GiB |
| two-card / off | 10.223 GiB | 12.296 GiB |
| single / fp16 | — | **15.050 GiB** |
| two-card / fp16 | 9.873 GiB | 14.922 GiB |

### E1: the two cards agree, bit for bit

All four E1 gates pass. The three probed tiles hash **identically across xpu:0 and xpu:1**, and each
card reproduces its own hashes across two consecutive passes (`gates.identity_across_cards: true`,
`gates.repeatable_per_card: true`). With both 9.700 GiB VAE replicas up, each card sits at **9.707
GiB allocated** (10.223 GiB peak) — inside the 12.5 GiB gate — and host peak RSS is **9.349 GiB**,
*below* a normal run's 12.467 GiB rather than 0.5 GiB above it, which is the receipt that building
copy B through `cross_card()` beats a second `from_pretrained`.

So the §1.4 worry — two B70s picking different GEMM kernels for the same shapes, as the FP8 lane has
seen — did not happen here. That is a real result and it is what licenses the next line.

### Lever 2 is exact, and it is worth nothing

The two-card decode reproduced **all four source hashes bytewise** (`video_tensor_sha256`
`ac730503b4380001…`, and audio, video latents and audio latents). §1.3's claim of
bit-identical-by-construction holds on hardware: the split was a clean 53/52 of 105 tiles, blended on
xpu:1, and the output is the same bytes the one-card fp32 path produced.

And it took **78.27 s against 79.31 s — 1.01x.** Not 1.98x, not 1.5x: nothing. Both replicas were
resident (9.700 GiB each), both cards' allocators show tile traffic, and the tiles were dispatched
53/52 — the work was divided and the wall time did not move, which means **the two worker threads
never overlapped**.

**Diagnosis (mine, from the shape of the result; not proven by a profile).** There is no lock of our
own in the worker — the two threads share no `nn.Module`, each owns its replica and its queue, and
the gather is positional. What they do share is the interpreter. The fp32 tile decode is a chain of
large, blocking GEMM calls; if the XPU op dispatch holds the GIL for the duration of the operation
rather than releasing it around the wait, then two Python threads driving two cards simply take
turns, and the measured wall time is the sum of the two halves plus epsilon — which is exactly
78.27 s. §1.3 step 2 assumed "torch releases the GIL"; on this stack, for this op, that assumption
is what failed.

**The lesson, stated for the next lane that reaches for it: Python threads do not parallelize two
XPU cards for fp32 GEMM-bound work.** A thread-per-card design measures as one card. Do not re-run
this experiment to re-learn it; if two cards must genuinely overlap, the design has to change.

**What would fix it: one OS process per card.** Two processes, each owning one card and one replica,
each handed the whole latent (~7 MB) and a list of tile indices, returning decoded tiles through
shared memory or a file; the parent blends. Separate interpreters cannot contend for one GIL, so the
53/52 split would translate into wall time and §1.5's 40.4-44 s prediction would get its fair test.
The cost is process setup, a second VAE load or a shared-memory hand-off of the weights, and host RAM
discipline on a 15 GiB box — real work, for a decode that fp16 already finishes in 16 s.

**Status: parked, not pursued.** Lever 2 stays in the code, defaulted off, with its exactness proven
and its speedup measured at 1.01x. If fp16 is ever rejected on fidelity grounds, the process-per-card
build is the exact path back to a ~40 s decode, and E1 has already cleared its hardest gate.

Note also that two-card + fp16 came in at **16.81 s — slower than single-card fp16's 15.93 / 15.34
s.** Same story plus the 2.85 s replicate, and the same conclusion: combining the two levers buys
nothing. The fp16 default, if it lands, is single-card fp16.

### E2: fp16 autocast is 5x, deterministic, and not exact

The repeat gate passes first, which is what makes the rest readable: the two fp16 runs are **bytewise
equal to each other** on all four hashes. fp16 autocast on these cards is deterministic, so this is a
different arithmetic, not a random one.

Speed: **15.93 s and 15.34 s** against the fp32 control's 79.31 s — **5.0x and 5.2x**, comfortably
past §5's "expect 35-50 s" gate. §1.2's reading of the decode as GEMM-bound fp32 (FFN 67 %,
projections 23 %, attention 10 %) is what this confirms: halving the GEMM width is nearly the whole
story, and the fused-attention bonus §4 predicted is on top.

Fidelity, against the fp32 control, from `vs-control-fp16-a-…json`:

| tensor | verdict | max\|d\| | mean\|d\| | differing |
|--------|---------|---------:|----------:|----------:|
| video | differs | 0.0295003 | 0.000115222 | 99.8323 % |
| audio | identical | 0 | 0 | 0 % |
| video latents | identical | 0 | 0 | 0 % |
| audio latents | identical | 0 | 0 | 0 % |

Worst frame 120; **124 of 124 frames differ.** Only the video changes, as it must — the audio VAE is
untouched and the latents are the input.

**What those numbers mean in 8-bit terms.** The compared tensor is the runner's `video_cpu`, and its
range is **[0, 1]**, not [-1, 1]: `_decode_and_write` un-normalises with the ImageNet mean/std and
clamps — `video = (video.float() * pixel_std + pixel_mean).clamp(0, 1)` (run_h3_t2v.py:4046) — and
the mp4 writer then multiplies by 255 (`run_h3_t2v.py:4075`). So **one 8-bit level is 1/255 =
0.003922**, and:

* mean\|d\| 0.000115222 = **0.029 of one 8-bit level** — about one thirtieth of the smallest
  difference an 8-bit pixel can express. The *typical* pixel is unchanged after rounding.
* max\|d\| 0.0295003 = **7.5 levels of 255** — the single worst pixel in 66.4 million (3 x 124 x 544
  x 960) moves by about 3 % of full scale.

(An earlier draft of this window's summary halved both figures by assuming a [-1, 1] range. The write
path above is the authority: [0, 1], so the levels are 1/255 apart and the numbers are the ones
above.)

"99.83 % of values differ" and "0.029 of a level on average" are the same fact said two ways:
essentially every pixel moves a little, and "a little" is far below what the file format can record.
The mp4 is x264 at crf 16 — lossy — so the encoder's own quantisation is larger than this difference
everywhere except that worst pixel. What it is *not* is bit-identical, and the receipts will say so
forever: `video_tensor_sha256` differs from the source run and always will.

**Memory: the one gate fp16 missed.** §5 gate 4 expected the peak to *fall*, on the argument that the
394 MiB fp32 score matrix halves. It rose: **15.050 GiB peak allocated against the fp32 path's 11.878
GiB**, +3.17 GiB. Autocast keeps the fp32 master tensors alive alongside the fp16 casts it makes per
op, and for a 9.700 GiB fp32 weight set that costs more than the score matrix saves. It still fits
with ~16.8 GiB free on a 31.891 GiB card, so it changes nothing operationally — but the gate as
written failed, and any future canvas increase should re-check it rather than assume fp16 is the
cheaper path in memory. (Gate 4 in §5 quoted the fp32 peak as "12.754 GiB"; that byte count,
12,754,005,504, is 12.754 **GB** and 11.878 GiB. The GiB figures above are the ones to use.)

**Status: NOT default.** `--vae-autocast` stays `off`. The recommendation put to the user is to make
fp16 the default with `--vae-autocast off` kept as the flag for any run that must reproduce an
existing hash, because it is the checkpoint's own documented recipe
(`autoencoder_kl_minimax_h3.py` docstring ~L529) which upstream enables only on CUDA
(`decoders.py:187`). **That decision is the user's and has not been made.**

### What a clip costs now

Substituting the measured fp16 decode into the 960x544 pruned run, everything else unchanged
(the phase times are the source receipt's; only `decode.video` moves):

| phase | today (fp32 decode) | with fp16 decode |
|-------|--------------------:|-----------------:|
| encode (tokenize + load + forward) | 13.62 s | 13.62 s |
| denoiser load (`load.stream` + skeleton) | 33.11 s | 33.11 s |
| `sample` (8 NFE) | 109.10 s | 109.10 s |
| `decode.load_vae` | 3.08 s | 3.08 s |
| **`decode.video`** | **79.96 s** | **15.9 s** (15.34-15.93) |
| audio VAE load + `decode.audio` | 3.34 s | 3.34 s |
| `write` | 1.56 s | 1.56 s |
| **total** | **243.8 s ≈ 4 min 4 s** | **~179.7 s ≈ 3 min 0 s** |

**Four minutes becomes three**, a 26 % cut, for a 5.17 s clip: 47.2 s of wall per second of video
becomes **34.8**. And the shape of the run changes with it. Decode was 33 % of the clip and is now
9 %. Model loading — 45.9 s of file reading that depends on neither the prompt nor the canvas, 49.4 s
counting both VAE loads — was 20 % and is now **27 %, the second-largest block in the run**.
`sample` was 45 % and is now **61 %**.

### Re-ranking what is left

| # | lever | gain / clip | exact | state after window 4 |
|---|-------|------------:|-------|----------------------|
| **4** | **batch mode / resident models: N clips in one process** | **~46-49 s per extra clip** | **yes** | **now the biggest exact lever.** Unbuilt, ~120 lines, §3 |
| **5** | two clips staggered through the block-24 hand-off | up to ~54 s amortised | yes | biggest *absolute* prize now that `sample` is 61 % — but high effort and pruned-only, §4 |
| **3** | overlap loads with idle cards | ~12-15 s | yes | still live, and now a larger share of a shorter run; but the VAE-copy half of it is dead with lever 2 |
| 1 | fp16 autocast decode | **measured, 64 s** | **no** | **done and measured.** Off by default; awaiting the user's call |
| 2 | two-card tiled decode | **measured, 1 s** | **yes, proven** | **parked.** Exact, 1.01x; needs process-per-card to pay |
| 6 | share the qkv activation rotation (int8) | ~2-5 s of 153 s | yes | on by default, **exact on CPU only — never measured on a card.** No int8 run since it landed |
| 7 | fast Hadamard rotation (int8) | up to ~25 s of 153 s | no | unchanged, unbuilt |

The order is now **4, then 5, then 3**, and the reasoning changed under it:

* **Lever 4 is first because loading is now 27 % of the clip and it is the only large saving that is
  exact by construction.** §3's arithmetic is unaffected by anything measured this window — the 49.4
  s of fixed load cost is the same 49.4 s — but it is now a quarter of the run instead of a fifth,
  and it is the one lever with no fidelity question attached. Its binding constraint is still host
  RAM: one decoded clip is 777 MB on a 15 GiB host, so phase C must write and free each clip before
  decoding the next. Window 4 measured host peak RSS at 9.349-10.066 GiB across these runs, which is
  the headroom batch mode has to work inside.
* **Lever 5 is now the largest number on the page** (`sample` is 109 s of a 180 s clip, and one card
  is idle for all of it), and it is still the dearest build, still pruned-only, and still gated on the
  same synchronous `cross_card()` that serialises the hand-off. Read it alongside the lever 2 result:
  §4's stagger also plans to drive two card-halves from two Python threads. **It will hit the same
  wall.** Whatever unblocks lever 2 — separate processes — is a prerequisite for lever 5, which moves
  the process-per-card work from "not worth it for decode" to "on the path to the biggest remaining
  lever". That is the strongest argument for building it.
* **Lever 3 shrinks.** Of §1.5's two overlap ideas, hiding copy B's build under card A's first tiles
  is now pointless — there is no copy B in the default path. What remains is the card-1 denoiser shard
  loading during `encode`, which is most of the 12-15 s and is unaffected.
* **Lever 6 has no measurement.** It is on by default on the strength of a CPU bitwise test, and no
  int8 run has been made since. The claim "2-5 s of 153" is still arithmetic from operand sizes. The
  cheapest way to settle it is one int8 960x544 run with the flag off against the existing
  `smoke-20260919T225400Z` receipt: same hashes (the CPU test says it must be), and a `sample`
  difference that is either there or is not.

### Costs of this window, for the record

Six GPU runs in 10 minutes of card time, plus the CPU tile-loop test. rc 0 throughout, no `xe` fault
lines, the watchdog never fired, host MemAvailable low-water 10,232 MiB. The `--decode-only` path is
what made it affordable: each run is ~1.5 min instead of ~4, because the 109 s of sampling is
replaced by reading one `tensors.safetensors`. And the control proved that substitution honest before
any of it counted — single-card fp32 `--decode-only` reproduced all four source hashes, so
decode-only is a faithful stand-in for the decode half of a full run.

## What this memo does not claim

No profile was taken: every FLOP and byte count above is arithmetic from shapes, and the only
measurements are the receipts, the `[vram]` lines and the phase timings. The int8 path's +43.8 s is
*attributed* to dequant traffic, rotation shape and the runtime LoRA by their relative sizes, not
decomposed by measurement. The 93.9 TFLOP/s and the 50 % idle fraction both follow from the strictly
serial block-24 hand-off — if a profile shows the cards overlapping at all, both move and lever 5's
headroom shrinks. Nothing here changes `smoke_h3.sh`, the receipt schema, or the repeat gate.
