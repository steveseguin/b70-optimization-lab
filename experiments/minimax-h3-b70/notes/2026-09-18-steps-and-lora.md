# The step count, and the 8-step turbo LoRA (2026-09-18)

Two open questions closed, both on CPU: no GPU was touched, no service or container was started or
stopped, nothing was downloaded by this session, and the only tensor data read was 208 four-byte
`alpha` scalars plus a ~1.2 MB slice the pre-existing ConvRot test already read.

The short version, in plain words:

* **`--steps 50` was not just a guess, it was off by one in a way nobody would have noticed.** In
  this scheduler the number you pass counts *grid points*, and the last one is the finished image,
  so the model actually runs one time fewer than the number says. Every step count published
  anywhere for MiniMax-H3 is the *other* kind of count, so each one needs a +1 here.
* **The base model's own number is 50 model passes, i.e. `--steps 51`.** That is now the default.
* **There is no CFG / guidance setting to get right.** The released weights have guidance baked in;
  the diffusers pipeline has no such knob at all, and each step is a single forward pass.
* **The 8-step turbo adapter is on disk and wired up.** With it, 8 model passes is the right
  number, i.e. `--steps 9` — which is what the smoke script now uses, and only because the adapter
  is applied. Without the adapter it falls back to 51.
* **On the INT8 build the adapter cannot be merged into the weights**, so it is applied as a
  separate small correction while the model runs. That is a real difference from the BF16 build and
  is documented below rather than hidden.

---

## 1. `num_inference_steps` counts sigma grid points, not model evaluations

This is the finding that matters, and it is in the scheduler's own docstring on this host:

> `/mnt/fast-ai/build/diffusers-src/src/diffusers/schedulers/scheduling_minimax_h3.py:133-136`
> ("The grid is `linspace(1, 0, num_inference_steps)` pushed through the exponential shift, with
> consecutive duplicates collapsed. The terminal `0` is already part of that grid ... so the
> schedule holds `num_inference_steps` sigmas and drives **`num_inference_steps - 1` model
> evaluations**, exposed as `self.timesteps = 1 - sigmas[:-1]`.")

and again in the argument description at `scheduling_minimax_h3.py:140` ("Number of sigma grid
points, terminal `0` included") and in the class docstring at `:25-27` ("the terminal zero is part
of the requested step count"). The code agrees: `:156-159` builds `torch.linspace(1.0, 0.0, N)`,
and `:167` sets `self.timesteps = (1.0 - sigmas[:-1])`, i.e. `N - 1` entries. Verified by reading
the file, not by inference.

The diffusers docs say the same thing (`docs/source/en/api/pipelines/minimax_h3.md:77`, a git blob
in this sparse checkout: "**`num_inference_steps` counts sigma grid points**, the terminal `0`
included, so it drives one model evaluation less"), and upstream's own runner applies the +1
explicitly:

> `ModelTC/Minimax-H3-Turbo/inference_minimax_h3.py:1140-1142`
> `# MiniMaxH3Scheduler interprets num_inference_steps as sigma grid points,`
> `# including terminal zero. N transformer evaluations therefore need N + 1.`
> `scheduler_grid_points = args.inference_steps + 1`  (passed at `:1170`)

**So every published MiniMax-H3 step count is NFE (number of transformer evaluations) and must be
entered here as NFE + 1.** The old `--steps 50` was 49 NFE.

### Where the numbers come from

| Configuration | NFE (published) | `--steps` here | Source |
| --- | --- | --- | --- |
| Base model, reference runner | 50 | **51** | `ModelTC/Minimax-H3-Turbo/DIFFUSERS_SETUP_AND_INFERENCE.md`, "Base model, 50 NFE": `--inference-steps 50` |
| Base model, official ComfyUI template | 20 | 21 | `Comfy-Org/workflow_templates/templates/video_minimax_h3_t2v.json`, node `137 PrimitiveInt [20]` -> `124 BasicScheduler`, with the `turbo_mode` boolean shipped `false` |
| 8-step turbo LoRA | 8 | **9** | `ModelTC/Minimax-H3-Turbo/README.md` spec table, row "FL2VA Turbo 8-step v1.0": distillation NFE 8, recommended inference NFE "8 / 4"; `DIFFUSERS_SETUP_AND_INFERENCE.md` "LoRA, 8 NFE (v1.0)" -> `--inference-steps 8`; ComfyUI template's `turbo_steps` widget pre-filled `8` |
| 4-step turbo LoRA | 4 | 5 | same spec table; ComfyUI r2v template `144 PrimitiveInt [4]` |

**Nothing on this host declares a default.** The diffusers block marks it required
(`modular_pipelines/minimax_h3/before_denoise.py:1129`,
`InputParam.template("num_inference_steps", required=True)`), and the template it draws from is the
library-wide generic value, not a MiniMax number
(`modular_pipelines/modular_pipeline_utils.py:395-399`, `"default": 50`). The model card
(`/mnt/fast-ai/llm-models/minimax-h3/README.md`) and its reproducible request scripts expose only
`short_edge`, `aspect_ratio`, `duration_seconds` and `seed` — no step count. The test suite's
`num_inference_steps: 2` (`tests/modular_pipelines/minimax_h3/test_modular_pipeline_minimax_h3.py:186`)
is a CPU toy value, not a recommendation. So the old comment ("the real default is unknown") was
accurate about *this host*; the answer had to come from upstream, and it did.

### What is now set

* `run_h3_t2v.py`: `DEFAULT_STEPS = 51`, `TURBO_STEPS = 9`. `--steps` defaults to 51 and its help
  text states the grid-point convention.
* `smoke_h3.sh`: `STEPS` defaults to **9 when a LoRA is applied** and **51 when it is not**. The two
  move together on purpose — a short step count without the distilled adapter is just a bad clip.
* The dry run prints `N sigma grid points -> N-1 transformer evaluations (NFE)` and, with `--lora`,
  flags a mismatch against 9.
* `receipt.json` records `num_inference_steps`, the derived `num_function_evaluations`, and a note
  carrying the convention.

## 2. There is no guidance / CFG setting

The released checkpoints are CFG-distilled, and diffusers exposes no guidance parameter at all:

* `modular_pipelines/minimax_h3/modular_pipeline.py:166-167` — "The checkpoint is
  guidance-distilled: guidance is baked into the weights, so there is no guider, no
  `negative_prompt` and no `guidance_scale`, and every step runs exactly one forward pass."
* `modular_pipelines/minimax_h3/denoise.py:52-55` — same statement for the denoise block.
* `docs/source/en/api/pipelines/minimax_h3.md:70`; `tests/.../test_modular_pipeline_minimax_h3.py:175`.
* `/mnt/fast-ai/llm-models/minimax-h3/README.md:181` — "The released checkpoints are CFG-distilled
  Omni Transformer model weights."
* ComfyUI drives it through `BasicGuider` + `SamplerCustomAdvanced`, a guider with no cfg widget.

So there is nothing to pass and nothing to tune. `run_h3_t2v.py` already ran cfg-free; this just
confirms it was right, and the dry run now says so. (In a UI that forces a cfg number, 1.0 is the
only value equivalent to the single-pass path — **inferred**, not quoted anywhere.)

## 3. Shift and sampler: unchanged, and confirmed

* **Video shift 12.0, audio shift 3.0.** `scheduling_minimax_h3.py:74` (`def __init__(self, shift:
  float = 12.0)` — the *only* ctor argument; there is no `num_train_timesteps`, no
  `use_dynamic_shifting`, no `base_shift`/`max_shift`, no `shift_terminal`), `:65-67` ("The released
  checkpoints use `12.0` for video latents and `3.0` for audio latents"), and both local configs:
  `/mnt/fast-ai/llm-models/minimax-h3/scheduler/scheduler_config.json` -> `"shift": 12.0`,
  `.../audio_scheduler/scheduler_config.json` -> `"shift": 3.0`. Upstream origin is
  `FL2VA/model_index.json`'s `"sigma_shift_scales": {"video": 12.0, "audio": 3.0}`; ComfyUI's
  `supported_models.py` carries the same pair.
* **Sampler**: rectified-flow Euler with `eta = 0` (`scheduling_minimax_h3.py:32`, `:62`,
  `:223-235`); `t = 1 - sigma` with `t = 1` clean; `x0 = x_t + sigma * v` (data-ward velocity);
  the Euler update is the blend `x_next = r*x_t + (1-r)*x0`, `r = sigma_next/sigma`, in float32.
  ComfyUI's equivalent is `res_multistep` + `simple`, denoise 1.0.
* **Turbo caveat, documented**: the *768p* turbo variants were distilled at **video shift 6**
  (ModelTC spec table; `DIFFUSERS_SETUP_AND_INFERENCE.md` passes `--video-shift 6 --lora-alpha 128`
  for `*_768p_*`). The adapter on this host is the **non-768p 544p-trained** v1.0, distilled at
  **12 / 3**, so the stock shifts stay. Do not carry shift 6 over to it.
* Geometry defaults confirm what the dry run already computes: `num_frames` 124
  (`before_denoise.py:196-204`), 24 fps, 5-15 s, short edge 768, max 768x1344 = 1,032,192 px, axes
  multiples of 32, 16:9 without a keyframe.

## 4. The 8-step turbo LoRA

`/mnt/fast-ai/llm-models/minimax-h3-comfy/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors`
— 1,956,193,000 bytes, complete (the file size equals `8 + header_len + last data_offset` exactly,
which is the only real completeness test for a safetensors file). 624 tensors = **208 modules x
{`alpha`, `lora_A.weight`, `lora_B.weight`}**.

Its `__metadata__` states the contract, so none of the mapping below is guessed:

```
training_rank    128        training_alpha  8.0        training_scale  0.0625
base_model       "Comfy-Org/MiniMax-H3 minimax_h3_fl2va_bf16.safetensors"
source_format    "Diffusers PEFT LoRA"      target_format "ComfyUI generic LoRA"
qkv_fusion       "block diagonal B; concat A; alpha multiplied by 3"
swi_glu_mapping  "Diffusers [value;gate] -> ComfyUI [gate;value]"
```

Note the filename says `fl2v` but the metadata's `base_model` and ModelTC's spec-table row are
**FL2VA** (tasks FL2VA / T2VA), which is the partition this lane drives. The adapter covers the
shared block stack, so it applies to the text-only workflow.

### Key mapping — it needed no new name table

Every LoRA base is a *Comfy checkpoint module name*, which is exactly what `build_remap()` and
`build_quant_map()` already key on. So the plan is built by asking, for each destination the weight
loader already knows, "is there a pair whose base is the module this weight comes from?" The two
output-axis transforms the weights need are inherited unchanged:

| Comfy module (52 of each: 50 blocks + 2 token-refiner blocks) | LoRA shapes | diffusers destinations | transform |
| --- | --- | --- | --- |
| `attn.qkv_proj` | A `[384, 5376]`, B `[21504, 384]`, alpha 24 | `attn.to_q` / `to_k` / `to_v` | `row_slice` on B: `(0,7168)`, `(7168,14336)`, `(14336,21504)` |
| `attn.out_proj` | A `[128, 7168]`, B `[5376, 128]`, alpha 8 | `attn.to_out.0` | — |
| `mlp.fc1` | A `[128, 5376]`, B `[28672, 128]`, alpha 8 | `ff.net.0.proj` | `swap_halves` on B ( `[gate;value]` -> `[value;gate]` ) |
| `mlp.fc2` | A `[128, 14336]`, B `[5376, 128]`, alpha 8 | `ff.net.2` | — |

`adaln_proj` carries no LoRA. Both transforms act on `lora_B`'s **first** axis, which is the output
axis — the same axis the int8 per-row scale is indexed by, and the same argument that makes
`row_slice` / `swap_halves` safe there. `lora_A` is therefore always taken whole.

**Result (dry run, both denoisers): 208/208 pairs matched, 0 unmatched keys, 0 shape mismatches.**

* `--denoiser pruned`: **312 destinations, all merged** (52 x 6: qkv into three, out_proj, fc1, fc2).
* `--denoiser int8`: **12 merged** (the two token-refiner blocks, which Comfy leaves BF16 in both
  files) **+ 300 runtime** (the 50 quantized blocks).

### Scale

The effective multiplier is `user_scale * alpha / rank`. The file's alphas are 8.0 at rank 128 and
**24.0 at rank 384** for the fused qkv — "alpha multiplied by 3", exactly so that `alpha / rank`
stays `0.0625` everywhere, which is the file's own declared `training_scale`. `--lora PATH` uses
`user_scale = 1.0`; `--lora PATH:0.8` scales it. ComfyUI's template loads this adapter at strength
1, so 1.0 is the default here too.

### The two application paths, and why they are not the same arithmetic

**Dense BF16 weights are merged at load time, exactly.** `W' = W + s * (B @ A)`, with `W` widened
to float32 (bf16 -> float32 loses nothing), the product taken in float32, and **one** rounding into
the destination dtype. The product is formed on the destination card, not on the host: only the two
small factors cross the bus, and the `[out, in]` float32 transient (616 MB at worst, an `mlp.fc1`)
is paid in card memory — the resource this host has, unlike host RAM.

**INT8 ConvRot Linears cannot be merged.** The stored weight is `round(W R / s)` with a per-row
float32 scale. Folding a delta in would require re-quantizing the whole Linear, which replaces the
measured int8 error (sitting exactly at the rounding floor,
`notes/2026-09-17-*`) by a different and larger one, silently. So on that path the adapter stays an
**additive low-rank term evaluated per call**, inside `ConvRotLinear`:

```
y = dequant(W) x + scale * B (A x)
```

which is the LoRA's own definition. Costs: **2.294 GB resident** across the two cards (the three
qkv destinations each keep a copy of the shared `lora_A`, so the runtime rank there is 384 rather
than 128 — exact, three times the low-rank work, and the price of not assuming a block structure
the file only claims in a metadata string), plus one rank-`r` GEMM pair per Linear per step.

**The one silent way to get this wrong** is the rotation. The adapter adapts `W`, not Comfy's
rotated `W R`, so its term must be built from the **unrotated** activation. Feeding it the rotated
`x` still runs and still produces plausible numbers. `ConvRotLinear.forward` keeps `x` before the
rotation explicitly, and `test_lora.py` section 4 pins it by constructing both variants and
checking the module is measurably not the wrong one.

Consequence to keep in mind when comparing the two denoisers: **with `--lora`, the pruned and int8
runs are no longer the same experiment in the same way they were.** Both apply the same adapter at
the same scale, but the pruned path folds it into the weights and the int8 path adds it at runtime
in float32, so the int8 path's adapter contribution is actually *more* precise than its base
weights. The receipt records which happened where.

### Tests

`scripts/test_lora.py` (CPU, headers + 208 alpha scalars, no GPU, no watchdog needed):

1. the merge against a **float64** reference — delta to float32 precision, merged weight within one
   bf16 ulp of the float64 truth, bitwise deterministic, and `scale 0` bit-identical to no LoRA;
2. the output axis — delta-of-slice == slice-of-delta, halves swap, the two compose in the weight
   loader's order, `lora_A` never sliced;
3. the runtime term against a float64 reference — with a float64 activation the whole path runs in
   float64 and reproduces the reference to 2.2e-16; `with_lora(x) - plain(x)` is exactly the
   low-rank term; bf16 tracks it to 2.2e-3; bitwise deterministic; bias lands after the term; four
   shape guards fail closed;
4. the rotation, as above;
5. the real turbo file — 208 pairs, 0 stray, every `alpha/rank == 0.0625`, and the full plan against
   both denoiser headers (312+0 and 12+300, qkv splitting into three disjoint row ranges, fc1
   carrying the swap);
6. `--lora PATH[:scale]` parsing, including a path that itself contains a colon.

`smoke_h3.sh dry` runs it alongside the existing ConvRot test. Both pass.

## 5. What is still not answered

* **Nobody has rendered a clip yet.** These numbers are read off files, and the GPU is still halted
  by the 2026-09-18 copy-engine fault. The step count being right does not make the pipeline right.
* **20 NFE vs 50 NFE for the base model** is a judgement call, not a fact: 50 is the reference
  runner's figure, 20 is what the official ComfyUI template ships. 51 is the default here because it
  is the conservative one; drop to 21 if first light is too slow and quality holds.
* **Whether the turbo adapter's quality holds at 256x448** (the smoke canvas) is untested — it was
  distilled at 544p.
* **The int8 + LoRA combination has never run.** The runtime term is proved correct on CPU; its
  cost per step on the cards is unmeasured.
