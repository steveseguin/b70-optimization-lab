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

## What this memo does not claim

No profile was taken: every FLOP and byte count above is arithmetic from shapes, and the only
measurements are the receipts, the `[vram]` lines and the phase timings. The int8 path's +43.8 s is
*attributed* to dequant traffic, rotation shape and the runtime LoRA by their relative sizes, not
decomposed by measurement. The 93.9 TFLOP/s and the 50 % idle fraction both follow from the strictly
serial block-24 hand-off — if a profile shows the cards overlapping at all, both move and lever 5's
headroom shrinks. Nothing here changes `smoke_h3.sh`, the receipt schema, or the repeat gate.
