# MiniMax-H3 pipeline plan for the two-B70 host (2026-09-17)

Read-only investigation. Nothing was run on a GPU, no service or container was started or stopped,
no weights were downloaded, and no tracked file was modified. Sources are the files already on this
host plus one read of the public diffusers documentation page for the pipeline; every claim below
either cites a file path or is marked unknown.

**Blocking operational fact first.** Both B70s are currently held by the live FP8 service:
container `neural-fp8-2cecb9151de5451583bda0fc8e66d076`, `--tensor-parallel-size 2`,
`--gpu-memory-utilization 0.95`, `ZE_AFFINITY_MASK=0,1`, listening on `127.0.0.1:18124`
(`CURRENT.md`, "Two-B70 host, September 17 23:46 UTC"). There is no free VRAM on this host while it
runs, and `AGENTS.md` forbids cycling it casually. Nothing in section 4 can start until the user
decides either to stop that service for a MiniMax block, or to move this lane to the four-B70 host.
Host RAM is also 15 GiB total with about 10 GiB already resident for that service (`free -g`).

---

## 1. What the official pipeline expects

### Pipeline classes

From `/mnt/fast-ai/llm-models/minimax-h3/model_index.json` and `modular_model_index.json`
(identical content):

- `_class_name`: `MiniMaxH3ModularPipeline`, `_blocks_class_name`: `MiniMaxH3Blocks`
- `_diffusers_version`: `0.36.0.dev0` — a **diffusers main build**, not a release. There is no
  `DiffusionPipeline` half: the diffusers docs state MiniMax-H3 "is integrated as Modular Diffusers
  blocks only … the blocks and their `MiniMaxH3ModularPipeline` are the whole integration".
- Components and their classes:
  | key | library | class | subfolder on disk |
  | --- | --- | --- | --- |
  | `text_encoder` | transformers | `Qwen3VLForConditionalGeneration` | `text_encoder/` (json+txt only here) |
  | `tokenizer` | transformers | `Qwen2TokenizerFast` | `tokenizer/` ✓ |
  | `processor` | transformers | `Qwen3VLProcessor` | `processor/` ✓ |
  | `vae` | diffusers | `AutoencoderKLMiniMaxH3` | `vae/` ✓ (10.4 GB, 3 shards) |
  | `audio_vae` | diffusers | `AutoencoderKLMiniMaxH3Audio` | `audio_vae/` ✓ (0.61 GB) |
  | `transformer` | diffusers | `MiniMaxH3Transformer3DModel` | `transformer/` (downloading) |
  | `transformer_ref` | diffusers | `MiniMaxH3Transformer3DModel` | `transformer_ref/` (not fetched) |
  | `scheduler` / `audio_scheduler` | diffusers | `MiniMaxH3Scheduler` | `scheduler/`, `audio_scheduler/` ✓ |

- Library pin: the repo README front matter says `library_name: minimax-h3`, but no `minimax-h3`
  Python package is referenced anywhere in the downloaded tree; there is no `requirements.txt`,
  `setup.py` or pinned diffusers commit on disk. The GitHub repo `MiniMax-AI/MiniMax-H3` is linked
  from `README.md` for *skills/prompting* only. The real runtime requirement is
  **diffusers ≥ 0.36.0.dev0 (git main)** + a transformers new enough for `Qwen3VLForConditionalGeneration`
  (the text encoder config declares `transformers_version: 4.57.0.dev0`) + PyAV for reference media.
  The README's own recommended servers are SGLang (`sglang serve --model-variant fl2va`), vLLM and
  ComfyUI.

### Workflows and which components text-to-video needs

Three workflows on one blocks class (diffusers docs):
- `t2va` — prompt only; uses `transformer/`
- `fl2va` — prompt + `image` (first keyframe) and/or `last_image` (last keyframe); uses `transformer/`
- `ref2va` — prompt + ordered `references` (≤9 images, ≤3 videos, ≤3 audio, ≤12 total); uses `transformer_ref/`

`transformer/` therefore covers **both** the text-only and the first/last-frame modes the brief asks
about. Selecting the workflow at `from_pretrained(..., workflow="t2va")` (or `load_components(workflow=...)`)
loads only that partition; a bare `load_components()` pulls **both** ~61.7 GiB partitions.

Components used for first/last-frame mode: `text_encoder` + `tokenizer` + `processor`
(+ `image_processor`/`video_processor`), `vae` (encodes the keyframes, decodes the video),
`audio_vae` (decodes the soundtrack), `transformer`, and **both** schedulers.

### Sampling, guidance, resolution, frames, fps

- **Guidance: none.** Both transformer partitions are guidance-distilled: "guidance is baked into the
  weights, there is no guider, no `negative_prompt` and no `guidance_scale`, and every step runs
  exactly one forward pass" (diffusers docs; the repo README says "The released checkpoints are
  CFG-distilled Omni Transformer model weights"). One model evaluation per step — a 2× saving versus
  a CFG model, and it means no batch-of-2 trick is needed.
- **Two schedulers, one transformer call per step.** `MiniMaxH3Scheduler` with `shift=12.0` for video
  (`scheduler/scheduler_config.json`) and `shift=3.0` for audio (`audio_scheduler/scheduler_config.json`).
  Both are stepped inside a single transformer call, because video and audio latents live in one
  packed sequence.
- **`num_inference_steps`: UNKNOWN.** It is a documented input ("counts sigma grid points, the
  terminal `0` included, so it drives one model evaluation less") but no default value appears in any
  file on this host or on the docs page, and the official request scripts do not expose it —
  `/mnt/fast-ai/llm-models/minimax-h3/scripts/readme/*.sh` only send
  `{task, prompt, conditions[], target:{short_edge, aspect_ratio, duration_seconds}, seed}` to an
  SGLang endpoint. Get the real default from `pipe.doc` after install, or from the diffusers source.
  Indirect evidence that the base is many steps: Comfy-Org ships 4-step and 8-step "turbo" LoRAs
  (`minimax_h3_fl2v_turbo_4step_…`, `…8step…` in `/mnt/fast-ai/llm-models/minimax-h3-comfy/README.md`).
- **fps: 24, fixed.** Duration 4–15 s per the repo README table; the diffusers blocks enforce **5–15 s**.
- **`num_frames` is snapped up to the next `17 * n + 5`** the video VAE can decode. The smallest legal
  request is therefore **124 frames (n=7, 5.167 s)** — the docs' own examples all use 124. There is no
  25-frame smoke clip available through the blocks (see the note in section 4).
- **Canvas:** `canvas_short_edge` default **768**, `canvas_max_pixels` **1032192** (= 1344×768),
  `reference_image_short_edge` 2048. `height`/`width` must be multiples of 32 and default to
  MiniMax-H3's canvas for the first keyframe's aspect ratio (16:9 without one). The docs note
  960×544 runs about 2.3× faster per step than 1344×768. Output audio is 32 kHz stereo
  (`audio_vae/config.json`: `sampling_rate: 32000`).
- **Seeding:** "One generator, three draws" — conditioning noise, then video noise, then audio noise,
  all from the passed `generator`; the same generator state returns the same video and soundtrack.
  This is the determinism hook for the repeat gates in section 4.
- **2K output is not open source.** H3-Regenerate-2K and H3-Context-IR are hosted APIs
  (repo `README.md`); only 768p H3-Base is local. The prompt the model expects is the *Context-IR
  expansion*, i.e. the long structured `integrated_multimodal_description / overall_soundscape /
  non_diegetic_music` text visible in `scripts/readme/reproducible-768p-t2va-request.sh`. Writing
  those by hand is covered by `docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md` and `…_ref_en.md`.

### The text encoder's role, and the vision tower

- H3 uses **Qwen3-VL-32B's unnormalized hidden state after decoder layer 50**, not the last layer,
  and the LM head is unused (repo README "H3-Encoder … hidden states from its 50th layer"; diffusers
  docs say the same). Confirmed on disk from the Comfy repackage's own metadata:
  `/mnt/fast-ai/llm-models/minimax-h3-comfy/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors`
  carries `__metadata__ = {"minimax_h3_te": "{\"num_hidden_layers\": 50, \"output\": \"unnormalized_hidden_after_layer_50\"}"}`,
  holds exactly `model.layers.0…49`, and has **no `lm_head`**.
- The denoiser's `text_dim` is 5120 (`transformer/config.json`), matching the Qwen3-VL text
  `hidden_size` of 5120 (`text_encoder/config.json`). Layers 50–63 and the LM head are dead weight.
- **Vision tower for text-only prompts: not needed, but cheap.** The tower is a 27-layer,
  1152-wide ViT (`vision_config` in `text_encoder/config.json`) plus three deepstack mergers.
  In the Comfy INT8 file the whole visual stack is kept in BF16 and totals about **1.19 GB**
  (`visual.blocks` 0.823 GB + `visual.deepstack_merger_list` 0.269 GB + `visual.merger` 0.090 GB +
  patch/pos embeds), so it costs little to keep. For `fl2va` with real keyframes and for `ref2va` it
  **is** required: the repo README states visual inputs are encoded by both the H3-Encoder and the
  H3-VisualVAE. The official int8 recipe in the diffusers docs deliberately leaves `model.visual`
  unquantized (`modules_to_not_convert=["model.visual", …]`).

### Derived sequence geometry (useful for sizing, all from configs)

- Video VAE (`vae/config.json`): `spatial_downsample_factors [2,2,2,2,1,1]` → 16×,
  `temporal_downsample_factors [1,2,2,1,1,1]` → 4×, `latent_channels 24`, `clip_length 17`,
  `token_drop 3`, ViT decoder of 36 layers × 2048 dim × 32 heads.
- Transformer patchifies latents by `[1,2,2]` → effective **32× spatial, 4× temporal**.
- Audio VAE: `encoder_rates [2,4,4,5,5]` = 800, so 32000/800 = **40 latent rows per second per channel**,
  `latent_channels 32` (matches `audio_in_channels: 32`).
- So a 124-frame clip is ≈31 latent frames. At 256×256 that is 8×8 = 64 tokens per latent frame,
  ≈2.0k video tokens. At the trained 1344×768 canvas it is 42×24 = 1008 per latent frame,
  ≈31k video tokens for 5.17 s and ≈91k for 15 s, plus ~207 audio rows per channel per 5.17 s, plus
  the text tokens (the official Context-IR prompts run 1k–5k tokens). Full attention only in this
  release; the sparse-attention implementation is not published yet (repo README).

---

## 2. Memory plan for two 32 GiB cards

Sizes below use GB = 10⁹ bytes and GiB = 2³⁰; the diffusers docs' "61.7GB" and "62.1GB" are actually
GiB (62.1 GiB = 66,714,780,128 bytes, which is exactly the `total_size` in
`text_encoder/model.safetensors.index.json`). Card capacity is 32 GiB = 34.36 GB each, 68.7 GB total.

| Artifact | On-disk size | Fits? |
| --- | ---: | --- |
| BF16 denoiser `transformer/` | 66.3 GB (61.7 GiB) | **No** — exceeds 64 GiB before any activation |
| INT8 ConvRot denoiser (Comfy, full) | 34.0 GB (31.7 GiB) | Yes, ~15.8 GiB/card, ~16 GiB/card free |
| "Pruned" BF16 denoiser (Comfy/unsloth) | 40 GB (37.3 GiB) | Yes, ~18.6 GiB/card, ~13 GiB/card free |
| INT8 ConvRot text encoder | 27.1 GB (25.3 GiB) | Yes on **one** card alone, ~7 GiB free |
| Video VAE fp16 / INT8 ConvRot | 5.21 GB / 2.81 GB | Yes |
| Audio VAE fp32 | 0.61 GB | Yes |

**Sequence.** Host RAM (15 GiB, ~4 GiB free today) rules out the documented consumer recipe, which
expects "around 75 GB" of host RAM for group/CPU offload. Everything must be resident in VRAM in
phases, loaded straight from NVMe:

1. Load the INT8 text encoder on one card (25.3 GiB, ~7 GiB headroom for a 5k-token prompt) — or
   split it across both cards if the headroom proves too tight. Encode the prompt (and keyframe
   images for `fl2va`), keep only the layer-50 hidden state (a few MB).
2. Free it completely (`del` + `torch.xpu.empty_cache()`), verify with an allocator readout.
3. Load the denoiser split across both cards, run the sampler, keep the video and audio latents.
4. Free it, load the video VAE + audio VAE on one card, decode last.

Loading must be **mmap + per-tensor `.to(device)`** (`safetensors.safe_open`), never a full state
dict in host RAM. `load_state_dict` into a meta-initialised module, tensor by tensor, is the pattern.
Do not let this swap: 35 GiB of swap exists but paging a 27 GB load would dominate the run, and
`AGENTS.md` forbids touching swap settings.

**The split itself** is the LTX lane's pattern: put whole blocks on each card, balance by bytes, and
move only the activation at the boundary. `experiments/ltx25-b70/scripts/ltx_layer_shard.py` picks
`split_index` by minimising `abs(non_block + 2*sum(block_bytes[:n]) - sum(block_bytes))` — reuse that
formula. With 50 layers of roughly equal size, the split is near layer 25, plus the non-block
parameters (proj_in, audio_proj_in, context_embedder, time embedder, 2 refiner layers, norm_out,
proj_out, audio_proj_out) on the primary card.

### What "ConvRot INT8" is

There is **no ComfyUI source anywhere on this host** (`find / -maxdepth 6 -type d -name "ComfyUI*"`
returns only `/mnt/fast-ai/src/intel-llm-scaler-20260815/omni/ComfyUI-OmniXPU`; the LTX lane's
ComfyUI tree at `/home/steve/src/ComfyUI-ltx25-baseline` and its venv
`/home/steve/.venvs/ltx25-baseline` live on the **four-B70 host**, not here). So the format was read
directly out of the safetensors headers of the two ConvRot files that are already complete:

- `/mnt/fast-ai/llm-models/minimax-h3-comfy/vae/minimax_h3_video_vae_int8_convrot.safetensors` (2.81 GB)
- `/mnt/fast-ai/llm-models/minimax-h3-comfy/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors` (27.14 GB, finished during this investigation)

Both encode the scheme identically. Every quantized `Linear` carries a sibling **`<name>.comfy_quant`**
tensor, a U8 array of 72 bytes whose content is ASCII JSON:

```json
{"format": "int8_tensorwise", "convrot": true, "convrot_groupsize": 256}
```

Layout per quantized Linear:

- `weight` — `I8`, shape `[out, in]` (identical to the BF16/FP16 shape; the rotation preserves shape)
- `weight_scale` — `F32`, shape `[out, 1]`, i.e. **per-output-row**, despite the "tensorwise" label
- `bias` — left unquantized (F32 in the VAE file, BF16 in the text encoder)
- everything else (norms, embeddings, conv stacks, the vision tower) left in F16/BF16/F32

Coverage: in the text encoder, 350 Linears = 50 layers × {q,k,v,o,gate,up,down}, 24.38 GB of I8 plus
2.75 GB BF16 (embed_tokens 1.56 GB + the visual tower + norms). In the video VAE, 144 Linears =
36 ViT-decoder blocks × {to_qkv, to_out, ff.w1, ff.w2}, 2.42 GB of I8; the conv encoder/decoder stays
F16. Note the VAE file's `__metadata__` also carries the upstream `source_config`
(`AutoencoderKLLegacy`, `vae_ratio 16`, `vae_ratio_t 4`, `use_vit_decoder true`), which is a useful
cross-check on the diffusers `vae/config.json`.

**What "convrot" means, and what is unknown.** No rotation matrix is stored anywhere in either file,
and the group size 256 divides every quantized input dimension (2048/256=8, 5120/256=20,
25600/256=100). That is the signature of a QuaRot/SpinQuant-style *rotation-then-quantize*: an
orthogonal transform `R` (almost certainly a size-256 Hadamard, applied block-diagonally along the
input axis) is folded into the weight offline as `W' = W R` so the weight's outliers are spread before
INT8 rounding, and the runtime must apply the matching `R` to the activation (`x' = x R`) before the
GEMM, since `x' W'ᵀ = x R Rᵀ Wᵀ = x Wᵀ`. **The exact transform is unknown from the files alone** —
it is generated in ComfyUI's code, which is not on this host. Whether the row scale is applied before
or after the rotation is likewise unknown.

This is cheaply recoverable offline, CPU-only, from files already on disk: we hold **both** the FP16
and the INT8 ConvRot video VAE, i.e. the same weights before and after the transform. For one layer,
dequantize `W' = weight.float() * weight_scale`, take a 256-column group `g`, and least-squares solve
`W[:, g] R_g = W'[:, g]` (rows ≫ 256, so it is heavily overdetermined). If every `R_g` comes back as
the same scaled ±1 Hadamard matrix, the format is fully pinned without ComfyUI. This is a read-only,
few-minutes NumPy job and should be step 0 of any ConvRot work.

**Can it be dequantized on the fly on PyTorch XPU without CUDA-only kernels?**

- The *dequantization* is portable: `w = q.to(torch.bfloat16) * weight_scale` is plain ATen and runs
  on XPU. The *rotation* is portable too: reshape to `[..., groups, 256]` and multiply by a 256×256
  Hadamard, or a fast Walsh–Hadamard — plain matmul/adds, no custom kernel.
- What is **not** portable is a fused INT8 GEMM. `torch._int_mm`, `torch._scaled_mm` and torchao's
  int8 kernels are CUDA-centric; XPU coverage is unverified here and should be treated as absent
  until measured. Comfy-Org's own README is the tell: "For diffusion models prefer `int8_convrot`
  **if you are able to use pytorch with cu130**" and "`fp8_scaled` should only be used if you cannot
  use `int8_convrot`" — the fast path is a CUDA build.
- So the realistic XPU path is **INT8 weights resident in VRAM, dequantized to BF16 per GEMM**. That
  keeps the 31.7 GiB footprint, costs an extra pass over each weight plus a transient BF16 buffer
  (largest: 25600×5120 = 262 MB in the text encoder, 14336×5376 = 154 MB in the denoiser FFN), and
  throws away most of the bandwidth benefit of INT8. Correct, but not fast. A `torch.compile`d
  dequant+matmul, or an oneDNN s8s8 path via a custom op, is the optimisation to try later — the lab
  already has oneDNN W4A16/W8A16 experience on the Qwen lane.

### The cheaper alternative to ConvRot: quantize the BF16 checkpoint ourselves

The diffusers docs give a **supported-loader** int8 recipe with no patches, listing exactly which
modules to leave alone:

```py
TorchAoConfig(Int8WeightOnlyConfig(version=2), modules_to_not_convert=[
    "proj_in", "audio_proj_in", "context_embedder", "time_embedder", "time_proj",
    "token_refiner", "norm_out", "proj_out", "audio_proj_out"])
# text encoder: modules_to_not_convert=["model.visual", "model.language_model.embed_tokens",
#                                       "model.language_model.norm", "lm_head"]
```

That list is also a free architecture map of `MiniMaxH3Transformer3DModel`. The catch is that the
documented call passes `low_cpu_mem_usage=False`, which this 15 GiB host cannot serve — so the
quantization would have to be done **offline in a streaming per-tensor pass** over the BF16 shards
(mmap one tensor, quantize, write, drop) producing our own int8 checkpoint on `/mnt/fast-ai`. That
avoids the unknown ConvRot rotation entirely and stays inside supported diffusers loaders, at the
cost of plain per-row int8 instead of rotation-assisted int8 (slightly worse quality at equal size).

---

## 3. What "pruned" means

**No documentation on this host says what `fl2va_pruned` removes.** `/mnt/fast-ai/llm-models/minimax-h3-comfy/README.md`
only lists the filenames; there is no NOTICE, no model card section, and the pruned files are not in
the download set (`/mnt/fast-ai/llm-models/minimax-h3-download.sh` fetches only
`minimax_h3_fl2va_int8_convrot.safetensors` and the int8 text encoder).

**Leading hypothesis, from arithmetic that matches exactly: "pruned" = the AdaLN branch weights, and
it is an inference-only removal, not a quality prune.** The repo README states:

> H3-Omni-Transformer is a 33B-parameter dense, single-stream Transformer, with approximately **13B
> parameters residing in AdaLN-related branches**. Because the AdaLN modulation outputs can be
> precomputed and cached, **these parameters do not need to be loaded for inference-only deployment**.
> We release the complete model weights to support further development, including fine-tuning.

Full BF16 = 66.3 GB (33B params). Pruned BF16 = 40 GB (≈20B params). Difference ≈ 26.3 GB ≈ **13.1B
BF16 parameters** — the README's AdaLN figure to two significant figures. The per-layer arithmetic
agrees: with `hidden_size 5376`, `ffn_dim 14336`, 56×128 heads and `time_embed_dim 2688`
(`transformer/config.json`), attention + FFN come to ≈347M per layer × 50 = 17.3B, which with the
2 refiner layers, `proj_in/out`, `audio_proj_in/out`, `context_embedder` (5120→5376) and the time
embedder lands right at the ≈20B / 40 GB the pruned build weighs. So "pruned" most likely means
*"the 13B of AdaLN modulation parameters have been dropped and replaced by their precomputed,
cached modulation outputs"* — lossless for inference, fatal for fine-tuning.

**Status: hypothesis, not established.** Two things could break it and both are cheap to check
before committing:

1. Read the pruned file's safetensors header (the header is the first ~100 KB — an HTTP range GET of
   the first megabyte from the Hub is enough, no 20 GB download) and diff its key list against the
   full INT8 file's. If the AdaLN keys are gone and new cached-modulation tensors appear, the
   hypothesis is confirmed.
2. If the cache is baked for a **fixed timestep schedule**, the pruned build is pinned to that step
   count and cannot be re-stepped. The header will show this: a cache tensor with a leading
   step-count dimension.

**If it holds, it changes the recommendation.** A 40 GB pruned **BF16** denoiser is 37.3 GiB — it
fits across two 32 GiB cards at ~18.6 GiB per card with ~13 GiB per card left for activations, with
**no quantization at all**, which is exactly the LTX lane's precedent (native BF16 transformer split
over two cards, bytewise-exact repeats). That would be a strictly better answer to "best quality that
fits" than INT8 ConvRot. The risk is runtime support: the pruned builds are ComfyUI artifacts, and
whether diffusers' `MiniMaxH3Transformer3DModel` can consume a checkpoint with no AdaLN branches is
**unknown** — the docs' int8 recipe explicitly quantizes the full checkpoint and says nothing about
pruned inputs. ComfyUI is the runtime designed for them.

Do **not** repeat the current lane README's claim that pruned "removes about 40% of the denoiser" with
unmeasured quality; that framing reads as a lossy prune and the evidence points the other way. It
should be corrected once check (1) is done.

---

## 4. Concrete stand-up sequence for this host

### Step 0 — prerequisites that are not GPU work

- **Get an exclusive window on the two cards.** The FP8 service on 18124 owns both at 0.95 memory
  utilization. This lane cannot start without an explicit user decision to stop it for a block of
  time (one controlled stop, per the `AGENTS.md` 2026-09-14 clarification — not a restart chain), or
  a decision to move the lane to the four-B70 host. Record whichever is chosen in `CURRENT.md`.
- **Finish and verify the downloads.** Still missing:
  `minimax-h3/transformer/*` (66 GB, in flight now — `/mnt/fast-ai/llm-models/minimax-h3-download-fix.sh`,
  log `/mnt/fast-ai/llm-models/minimax-h3-download.log`) and
  `minimax-h3-comfy/diffusion_models/minimax_h3_fl2va_int8_convrot.safetensors` (34 GB, queued
  behind it). `/mnt/fast-ai` has 171 GB free and both together take ~100 GB, so the end state is
  ~70 GB free — fine, but do not also pull the BF16 text encoder (67 GB).
  The `hf` CLI was used with no post-download hash gate. The LTX lane lost a transformer to silent
  corruption that passed size checks (`experiments/ltx25-b70/README.md`, "Input integrity failure
  before first generation": 79 changed bytes in one 8 MiB region). **Re-verify every large file
  against the publisher SHA-256 with fsync + O_DIRECT reread before first use**, using the logic in
  `/home/steve/b70-optimization-lab/experiments/ltx25-b70/scripts/download-verified.py`.
- **Recover the ConvRot rotation** with the FP16-vs-INT8 video VAE least-squares job described in
  section 2. CPU only, no GPU, no downloads. If it fails to resolve, ConvRot is blocked without a
  ComfyUI source tree and the plan falls back to our own streamed int8 quantization of the BF16
  checkpoint.

### Python environment

Build a fresh venv — **on `/mnt/fast-ai`, not on `/`** (root has only 23 GB free; a torch+oneAPI venv
is ~10 GB):

```
/mnt/fast-ai/venvs/minimax-h3        # new; python3.12, matching the other lanes
```

Mirror the LTX lane's captured runtime, which is the lab's proven PyTorch-XPU stack for a video
model — `/home/steve/b70-optimization-lab/experiments/ltx25-b70/data/environment.txt`:
`torch==2.14.0+xpu`, `torchvision==0.29.0+xpu`, `torchaudio==2.11.0+xpu`, `triton-xpu==3.8.0`,
`transformers==5.17.0`, `safetensors==0.8.0`, `numpy==2.5.2`, `av==18.1.0`, oneAPI 2026.1 runtime
wheels. Add on top: `diffusers` from **git main** (the checkpoint declares `0.36.0.dev0`; pin the
commit and record it), `accelerate`, `huggingface-hub`. Do **not** reuse or mutate
`/home/steve/.venvs/vllm-xpu` (torch 2.11.0+xpu, transformers 5.10.2) — it belongs to the FP8 lane.

**No container.** The lab's containers on this host are vLLM XPU images for the Qwen lane; none
carries diffusers or a video stack, and the LTX precedent is a plain venv plus a local server. A venv
keeps the oneAPI runtime pinned by wheels and avoids the docker shim entirely.

**ComfyUI is a second, separate option** (needed only if the ConvRot or pruned builds are chosen and
the rotation cannot be reproduced): install a pinned ComfyUI tree the way the LTX lane did
(`/home/steve/src/ComfyUI-ltx25-baseline` on the other host, core unmodified, behaviour added only in
custom nodes) and port the split as a custom node. That is a download and needs approval.

### Which LTX-lane scripts to copy from

All paths under `/home/steve/b70-optimization-lab/experiments/ltx25-b70/scripts/`:

| Script | What to take |
| --- | --- |
| `ltx_layer_shard.py` | The **split policy**, not the class. Byte-balanced `split_index` search; a per-forward transfer cache keyed on tensor identity so one activation crosses the PCIe boundary once; a boundary wrapper that moves the block's inputs to the shard's device and moves the last block's output back; an `ON_PRE_RUN` residency check that raises if any tensor is still on CPU; refusal of clones/patches/state-dict saving on a sharded model. It is written against ComfyUI's `ModelPatcher` and `LTXAVModel`, so on the diffusers path re-implement the policy as a plain `nn.Module` forward hook over `transformer.transformer_blocks`. |
| `download-verified.py` | Hash-gated fetch: network SHA-256, fsync, O_DIRECT persisted-bytes reread, then rename + parent fsync, one attempt, no retry loop. |
| `verify-repeats.py` | The repeat gate: ≥3 distinct run names, asserts deterministic mode was on and warn-only off, loads each run's `tensors.safetensors`, checks finiteness, re-hashes every tensor against the capture receipt, rejects degenerate output (`images.std() > 0.01`, not all frames identical), never overwrites a receipt. |
| `compare-clip.py`, `compare-clip-hash.py` | Reference-vs-candidate exact gate with recorded identity. Drop the ComfyUI `history/prompt_id/execution_cached` assertions; keep the tensor-hash and never-overwrite rules. |
| `export-lossless.py` | Exact float media export (FFV1 float video + float PCM) separate from the latency timer, with an independent decode round-trip receipt. |
| `profile-clip.py` | The receipt shape: boot-id and process-start binding, hashes of the model-verification and server-args files, a `FAULT.json` latch that halts new requests. |
| `kernel_fault_detector.py`, `per-device-probe.py` | Fault latching and per-device state. |

The lane README/PLAN pair in `experiments/ltx25-b70/` is also the template for how this lane's packet
should read (preregistered baseline, scope limits, evidence paths outside Git).

### First smoke test

Order matters — each step is a gate, and nothing advances past a failure:

1. **Loader smoke, no sampling.** Instantiate `MiniMaxH3Transformer3DModel` from
   `transformer/config.json` on `meta`, stream the checkpoint in tensor by tensor, place blocks on
   `xpu:0`/`xpu:1` per the byte-balanced split, and assert full residency. Record peak host RSS —
   this is where the 15 GiB RAM limit bites. Nothing is sampled yet.
2. **One transformer forward on a tiny packed sequence** (a few hundred tokens, random latents),
   shapes and dtypes only. This is where XPU op coverage for 3D MM-RoPE, the qk-norm and AdaLN shows
   up, and it costs seconds. There is no legal short clip through the blocks, so this is the
   substitute for the LTX lane's 25-frame probe.
3. **VAE round trip alone**: encode a still image, decode it back, on one card, at 256×256. Confirms
   `AutoencoderKLMiniMaxH3` and the ViT decoder run on XPU before the denoiser is in the picture.
4. **First real clip**: `t2va`, `height=256, width=256, num_frames=124` (5.167 s, the smallest legal
   request), `generator=torch.Generator().manual_seed(42)`, the step count left at the blocks'
   default, one of the short prompts from `docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md`. Expect it to
   be slow; the point is that it completes and produces non-degenerate frames and audio.
5. **Then `fl2va`** with a single first keyframe, same canvas and frame count.
6. Only then move the canvas up: 320×192 → 512×288 → 960×544 → 1344×768, recording seconds per clip
   at each, and stop where either card's free memory drops below a stated margin.

### Recording determinism and time

- **Determinism gate.** Fix the seed through one `torch.Generator` (the blocks make three draws from
  it in a fixed order). Enable `torch.use_deterministic_algorithms(True)` with warn-only off and
  fail closed; if an op has no deterministic XPU implementation, record the failure and qualify any
  revised claim explicitly — exactly the LTX preregistration wording. Save, per run, a
  `tensors.safetensors` holding **video latent, audio latent, decoded frames, waveform**, plus a
  `summary.json` with per-tensor SHA-256, the sample rate, the deterministic flags, the seed, the
  resolution/frame count, the resolved step count, the split index, and the component file hashes.
  Run ≥3 fresh recomputations of the same request under distinct run names and compare with the
  adapted `verify-repeats.py`. Report bytewise-equal or not; do not soften it to "visually identical".
- **Timing.** Separate (a) component load seconds per phase — text encoder, denoiser, VAE — from
  (b) encode, (c) sample, (d) decode, and report first-run versus repeat separately. The lane metric
  should be the LTX one: **seconds of wall per second of generated video** (a 124-frame clip is
  5.167 s of video), alongside seconds per sampler step. Evidence goes under
  `/mnt/fast-ai/bench-results/minimax-h3-<date>/`, never into Git; only summaries come back to the
  repo, per `AGENTS.md`.
- **Faults halt.** Keep a `FAULT.json` latch in the evidence root; any xe/GPU fault line stops new
  requests and no reset or reboot is attempted.

### Risks, ranked

1. **Card availability.** Both B70s are held by the live FP8 service. This is the first gate, and it
   is a user decision, not an agent one.
2. **Host RAM, 15 GiB.** The entire documented consumer path (group offload, `enable_auto_cpu_offload`,
   "around 75 GB of host RAM at int8") is unavailable. Every load must be mmap-streamed with a
   measured RSS ceiling, and the phases must not overlap. This is the single most likely cause of a
   failed bring-up.
3. **INT8 dequant on XPU.** No fused int8 GEMM should be assumed; plan for dequant-to-BF16 per GEMM,
   which is correct but surrenders most of INT8's speed. The ConvRot rotation is undocumented on this
   host and must be recovered empirically or read out of a ComfyUI tree that is not installed here.
4. **XPU op coverage in the denoiser.** 3D MM-RoPE over `(t,h,w)` with `rope_freq_dim 16`, qk-norm
   RMS with `qk_norm_eps 1e-5`, modality-specific AdaLN, and a packed sequence that mixes text,
   video and audio rows. Attention is the real exposure: `set_attention_backend("_flash_3_hub")` is
   CUDA-only, so XPU falls back to torch SDPA, and at the trained canvas the packed sequence is
   ~31k–91k tokens with **full attention only** in this release. Memory-efficient SDPA on XPU at
   those lengths is unverified — another reason to start at 256×256.
5. **The VAE decode.** A 36-layer, 2048-wide ViT decoder over the whole clip; at 768p this is its own
   sequence-length problem. The config's `clip_length 17` / `token_drop 3` suggest a clip-wise decode
   path exists — use it rather than decoding the full latent in one call.
6. **The pruned-build question (section 3).** If the AdaLN hypothesis holds and diffusers accepts the
   checkpoint, the whole INT8 effort is avoidable and a native BF16 split becomes the plan. Resolve
   this with the 1 MB header read **before** investing in ConvRot.
7. **Wall-clock expectations.** Even at the smallest legal request this is a 50-layer, ~20B-active
   denoiser over thousands of tokens for tens of steps, on two cards, with an INT8 path that
   dequantizes in software. Do not promise a clip time until one is measured; publish nothing until
   quality and determinism are labelled, per `AGENTS.md`.
8. **Disk.** ~70 GB free on `/mnt/fast-ai` after the pending downloads, and 23 GB on `/`. Keep
   evidence, any self-quantized checkpoint and the venv off the root filesystem.

### Open questions to close first

- `num_inference_steps` default (read `pipe.doc` after install).
- Exact ConvRot rotation (least-squares recovery from the VAE pair already on disk).
- What `fl2va_pruned` drops (1 MB header range read).
- Whether `transformer_ref/` is ever wanted here — `ref2va` is a second 66 GB partition and the brief
  is first/last-frame mode, so it should stay unfetched for now.
