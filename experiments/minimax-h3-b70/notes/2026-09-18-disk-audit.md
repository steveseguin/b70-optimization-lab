# MiniMax-H3 weights on disk: what is complete, what is not, and what the runner actually loads

Date: 2026-09-18 · read-only audit · no GPU, no container, no download, no service touched.
Method: every file under the two model directories was size-compared against the Hugging Face repo
listings (`https://huggingface.co/api/models/<repo>/tree/main?recursive=true&expand=true`, LFS
sizes, read-only), and the large safetensors were opened far enough to read the **header only**
(8-byte length + JSON) to confirm the declared tensor table ends exactly at the file's last byte.

## Headline

1. **The full INT8 ConvRot denoiser is NOT on disk.** `minimax_h3_fl2va_int8_convrot.safetensors`
   is 15.7 % downloaded -- 5.34 GB of 34.04 GB -- and what exists is an `.incomplete` file in the
   HF cache, not a usable checkpoint. The interrupted transfer stopped on 2026-09-17 around 21:02.
2. **The pruned BF16 denoiser is complete** (40.23 GB, 532 tensors, header consistent).
3. **The text encoder on disk is the Comfy INT8 ConvRot Qwen3-VL-32B** (27.14 GB, complete). The
   original BF16 text encoder was never downloaded: only its json/txt files are here, plus 6.89 GB
   of orphaned partial shards in the cache from the botched first download pass.
4. **`run_h3_t2v.py` loads the pruned BF16 denoiser, unconditionally.** `PRUNED_DENOISER` is a
   module constant with no flag to point it anywhere else.

## Table: /mnt/fast-ai/llm-models/minimax-h3 (`MiniMaxAI/MiniMax-H3`, diffusers root layout)

70 real files, and **every one is byte-for-byte the repo's size**. Nothing here is partial.

| Component | On disk | Repo | State |
| --- | ---: | ---: | --- |
| `transformer/` (BF16 FL2VA denoiser, 14 shards + index) | 66.281 GB | 66.281 GB | **complete** (reference/source; needs 4 cards to run) |
| `vae/` (video, 3 shards + index) | 10.416 GB | 10.416 GB | **complete** |
| `audio_vae/` | 0.605 GB | 0.605 GB | **complete** |
| `text_encoder/` json + txt (config, tokenizer, index) | 11.6 MB | — | **complete** (the config the runner reads) |
| `text_encoder/model-0000*-of-00014.safetensors` (BF16 Qwen3-VL) | **0 B** | 66.727 GB | **missing by design** -- `minimax-h3-download.sh` deliberately skips it for disk |
| `processor/`, `tokenizer/`, `scheduler/`, `audio_scheduler/` | 22 MB | 22 MB | **complete** |
| `model_index.json`, `modular_model_index.json`, `docs/`, `scripts/`, README, LICENSE | 0.1 MB | 0.1 MB | **complete** |
| `transformer_ref/` (Ref2VA denoiser) | **0 B** | 66.281 GB | not downloaded, not wanted (the lane is `t2va` on the FL2VA partition) |
| `assets/`, `FL2VA/`, `Ref2VA/` (the repo's second, non-diffusers copy) | **0 B** | ~365 GB | not downloaded, not wanted |

Orphaned partials in `.cache/huggingface/download/text_encoder/`: **8 shards, 6.885 GB total**
(5.6 % to 38.1 % each, shards 1-8 of 14), left by the first download pass, which passed several
patterns after one `--include` and so downloaded the whole repo until it was interrupted
(`hf` warned `Ignoring --include since filenames have being explicitly set`). They resume nothing
useful and are pure disk cost.

## Table: /mnt/fast-ai/llm-models/minimax-h3-comfy (`Comfy-Org/MiniMax-H3`)

6 real files, all byte-for-byte the repo's size.

| File | On disk | Repo | State |
| --- | ---: | ---: | --- |
| `diffusion_models/minimax_h3_fl2va_pruned_bf16.safetensors` | 40.226 GB | 40.226 GB | **complete** -- 532 tensors, header table ends exactly at EOF; largest tensor `blocks.0.mlp.fc1.weight` 308 MB |
| `diffusion_models/minimax_h3_fl2va_int8_convrot.safetensors` | **5.336 GB (15.7 %)** | 34.039 GB | **PARTIAL** -- an `.incomplete` in the cache, plus a stale `.lock`. **28.702 GB still to fetch.** Not visible under `diffusion_models/` and not loadable. |
| `text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | 27.141 GB | 27.141 GB | **complete** -- 1602 tensors, 350 quantized Linears, `__metadata__` `{"num_hidden_layers": 50, "output": "unnormalized_hidden_after_layer_50"}`; largest tensor `model.embed_tokens.weight` 1.556 GB |
| `vae/minimax_h3_video_vae_fp16.safetensors` | 5.208 GB | 5.208 GB | **complete** (562 tensors) |
| `vae/minimax_h3_video_vae_int8_convrot.safetensors` | 2.811 GB | 2.811 GB | **complete** (the ConvRot rotation was recovered from this pair) |
| `vae/minimax_h3_audio_vae_fp32.safetensors` | 0.605 GB | 0.605 GB | **complete** (917 tensors) |
| `text_encoders/qwen3vl_32b_minimax_h3_bf16.safetensors` | **0 B** | 51.506 GB | not downloaded |
| `diffusion_models/minimax_h3_fl2va_bf16.safetensors` | **0 B** | 66.280 GB | not downloaded (the same weights are already here in diffusers form) |
| `diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled` / `_pruned_int8_convrot` | **0 B** | 20.958 / 20.970 GB | not downloaded, lower fidelity than what is here |
| `loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | **0 B** | 1.956 GB | not downloaded -- see the recommendation |
| everything `ref2va*`, `model_patches/`, `embeddings/` | **0 B** | — | not downloaded, not wanted |

### Why the INT8 ConvRot denoiser is stuck at 15.7 %

`minimax-h3-download.log`, read end to end: the fix-up pass (`minimax-h3-download-fix.sh`) finished
the original transformer at 20:47:46 and then started the Comfy set (`Fetching 6 files`). That pass
**never printed its `comfy int8 rc=` line** -- the next log line is the separately launched
`minimax-h3-download-pruned.sh`, which ran 21:02 -> 21:29 and completed the pruned BF16 file. So the
INT8 ConvRot transfer was cut off about 15 minutes in, which matches 5.34 GB, and nothing resumed
it. It is a bookkeeping accident, not a repo problem or a disk-space failure.

## What `run_h3_t2v.py` actually loads

| Phase | File it opens | Source |
| --- | --- | --- |
| plan / load / receipt | `PRUNED_DENOISER` = `minimax-h3-comfy/diffusion_models/minimax_h3_fl2va_pruned_bf16.safetensors` | line 65, used at lines 808, 817, 845, 1119, 1130, 1233, 1306, 1439-1440 |
| encode | `INT8_TEXT_ENCODER` = `minimax-h3-comfy/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | line 66 |
| decode | `vae/` and `audio_vae/` of the **original** repo (not the Comfy fp16/fp32 copies) | lines 72-73 |
| config / tokenizer | `transformer/config.json`, `text_encoder/`, `tokenizer/` of the original repo | lines 69-71 |
| rotation | `data/convrot-hadamard-256.safetensors` (regenerable on CPU in seconds) | line 67 |

There is **no option** to select a different denoiser: `--help` has `--adaln-dtype`,
`--adaln-out-dtype` and `--te-rotation`, none of which change the file. So today the runner can
only run the pruned form, because the full INT8 ConvRot form is not on disk to run.

## Does that match the lane's fidelity goal? -- the one real contradiction

The task brief for this audit states the goal as *"full INT8 ConvRot denoiser, never a pruned one by
default"*. **The lane's own README says the opposite**, and says it with a measurement behind it:

> Fidelity rank on two cards: pruned BF16 > INT8 ConvRot ... The plan here is (1) [the pruned BF16
> denoiser] with the streamed BF16 encoder

backed by [the AdaLN exactness note](2026-09-17-adaln-table-exactness.md): the pruned form's rank-8
AdaLN table is an approximation whose worst error (8.0e-4 / 1.2e-3 on values spanning +-3.3 / +-7.3)
is *below the BF16 checkpoint's own error against float32* (4.0e-3 / 7.1e-3), while INT8 ConvRot
quantizes every weight in the denoiser.

I am not resolving that contradiction in a disk audit; it is a fidelity decision for the user. What
the audit can say is that it is **currently moot in the worst way**: neither goal is satisfiable as
a choice, because only one of the two denoisers exists on this host. Both statements agree that
having the full INT8 ConvRot file is worth 34 GB of disk:

* if the brief's ranking is right, it is the default and the lane cannot run its intended model;
* if the README's ranking is right, it is still the *only* on-two-cards control that isolates the
  pruned AdaLN re-parameterisation from everything else -- same canvas, same seed, same encoder,
  one difference. Without it the pruned form's quality claim rests on a header-level argument plus a
  CPU curve fit, never on two rendered clips.

One more thing to be honest about: having the file is not the same as being able to run it.
`run_h3_t2v.py` would need a second load path for it -- the full checkpoint keeps the unpruned AdaLN
branch (`time_embedder.linear_1/linear_2`, `adaln_proj` 2688 -> 96768), so the pruned-AdaLN module
swap must be skipped, the remap extended, and `plan_split`'s byte accounting redone for int8 weights
plus f32 scales. The `ConvRotLinear` class and the recovered Hadamard rotation already exist and are
reusable as they are. That is a session of work, not a flag.

## Recommendation -- what to download (do NOT run this during a GPU session)

**1. Finish the full INT8 ConvRot FL2VA denoiser (28.702 GB remaining; resumes the existing 5.34 GB).**

```bash
ionice -c 3 /home/steve/.local/bin/hf download Comfy-Org/MiniMax-H3 \
    --include "diffusion_models/minimax_h3_fl2va_int8_convrot.safetensors" \
    --local-dir /mnt/fast-ai/llm-models/minimax-h3-comfy
```

One pattern per `--include` -- that is the whole lesson of `minimax-h3-download-fix.sh`. At the
24.7 MB/s the pruned file averaged this is roughly 20 minutes; at the 5.9 MB/s the interrupted pass
was getting, roughly 80. Disk: `/mnt/fast-ai` has **53 GB free (94 % used)**, so this leaves ~24 GB.
Run it on its own -- it is I/O and page cache on a 15 GiB host, so not beside a GPU run.

**2. Optional, 1.956 GB: the 8-step turbo LoRA**, because `STEPS=8` is currently a guess stacked on
another guess (the base step count is undeclared anywhere on this host, see the stand-up note).

```bash
ionice -c 3 /home/steve/.local/bin/hf download Comfy-Org/MiniMax-H3 \
    --include "loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors" \
    --local-dir /mnt/fast-ai/llm-models/minimax-h3-comfy
```

**3. Not recommended now: the BF16 text encoder** (`text_encoders/qwen3vl_32b_minimax_h3_bf16.safetensors`,
51.506 GB, or the original repo's 66.727 GB shards). It would settle the unverified assumption that
the text encoder uses the same ConvRot rotation as the video VAE -- but it does not fit beside item 1
in 53 GB, and the GPU session settles the same question for free by running `--te-rotation none` as
the A/B control.

**4. Free 6.885 GB first, if disk is tight** -- the orphaned text-encoder partials resume nothing:

```bash
rm -f /mnt/fast-ai/llm-models/minimax-h3/.cache/huggingface/download/text_encoder/*.incomplete
```

(That is a suggestion for the user, not something this audit did. Nothing on disk was changed.)
