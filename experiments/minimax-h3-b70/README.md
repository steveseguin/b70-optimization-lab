# MiniMax-H3 on the two-B70 host: lane packet (opened 2026-09-17)

Status: **weights downloading; nothing run yet.**

## What the model is

[MiniMaxAI/MiniMax-H3](https://huggingface.co/MiniMaxAI/MiniMax-H3) is not a language model. It is a video-with-audio
generation system (text/image/reference to video, 4-15 s, 24 fps, 32 kHz stereo, license: MiniMax-H3 Community License):

| Component | Parameters / size (BF16) | Role |
| --- | ---: | --- |
| `transformer` (H3-Base-FL2VA, first/last-frame mode) | ~33B, 66.3 GB | the video+audio diffusion denoiser |
| `transformer_ref` (H3-Base-Ref2VA, reference mode) | ~33B, 66.3 GB | the reference-input denoiser (separate checkpoint) |
| `text_encoder` (Qwen3-VL 32B) | 66.7 GB | prompt and image understanding, run once per generation |
| `vae` (video), `audio_vae` | 10.4 GB, 0.6 GB | decode latents to frames and audio |

So the "llama.cpp or vLLM" question does not apply: it runs as a diffusers-style pipeline (PyTorch), or through
stable-diffusion.cpp with the GGUF builds. The lab's [LTX 2.5 lane](../ltx25-b70/README.md) is the precedent: a
PyTorch XPU pipeline with the BF16 transformer split across two cards and the encoder and decoder on others.

## What fits two 32 GiB cards without giving up quality

The BF16 denoiser alone (66 GB) does not fit two cards with activations. Third-party builds, largest first:

| Build | Denoiser | Text encoder | Notes |
| --- | ---: | ---: | --- |
| Comfy-Org `minimax_h3_fl2va_int8_convrot` | 34.0 GB (full, INT8 rotation-quantized) | `qwen3vl_32b_..._int8_convrot` 27.1 GB | the largest denoiser that splits across two cards; ComfyUI's INT8 ConvRot dequant would have to be ported to XPU |
| Comfy-Org `minimax_h3_fl2va_pruned_bf16` | 40.2 GB (BF16, **pruned**) | same | "pruned" = the timestep embedder and the blocks' AdaLN projections replaced by a `adaln_t_table [1025, 8]` plus per-block `adaln_proj` weights of 8 inputs instead of 2,688 (header comparison, 2026-09-17): the per-timestep modulation is re-parameterised through an 8-dimensional table. **Measured** ([note](notes/2026-09-17-adaln-table-exactness.md)): a rank-8 affine fit of the timestep-modulation curve, not exact; worst error 8e-4 / 1.2e-3 on values spanning +-3.3 / +-7.3 (blocks 0 / 25), *below* the unpruned BF16 weights' own error against float32 (4e-3 / 7e-3). ComfyUI interpolates the table linearly between the 1/1024 grid points; snapping would cost 5x more. Fidelity rank on two cards: pruned BF16 > INT8 ConvRot |
| unsloth `MiniMax-H3-FP8.pt` / Comfy `fl2va_pruned_fp8_scaled` | 20-21 GB (pruned + FP8) | same | quantized on top of the pruned form |
| unsloth GGUF `fl2va_pruned-Q8_0` | 20.0 GiB (pruned) | `qwen3vl_32b_minimax_h3-Q4_K_M` 17 GiB | stable-diffusion.cpp (SYCL backend exists); text encoder on CPU needs more than this host's 15 GiB RAM, so it would run on the second card |

The user's brief is best quality that fits comfortably, no quality loss by design. No two-card option is exact: the full BF16 denoiser needs four cards. Ranked by fidelity: (1) the **pruned BF16
denoiser (37 GiB) split across the two cards** (rank-8 AdaLN fit, error below the BF16 noise floor), (2) the full denoiser at
INT8 ConvRot (34 GB, quantization error), (3) pruned + FP8/GGUF. The text encoder can stay exact (BF16, 51.5 GB, streamed
layer by layer once per prompt) or use the INT8 ConvRot build (27 GB). The plan here is (1) with the streamed BF16 encoder,
and the full BF16 model on the four-card host as the reference for measuring the pruned form's actual output difference, with the INT8 text encoder run first on one card and
unloaded, and the fp16 video VAE (5.2 GB) plus audio VAE. The pruned builds are a fallback, not the plan, until their
quality is measured against the full one. The BF16 denoiser is kept as the reference/source (a BF16 reference run
needs the four-card host, 128 GiB).

## Downloaded to this host

`/mnt/fast-ai/llm-models/minimax-h3` (original: `transformer/`, `vae/`, `audio_vae/`, schedulers, processor,
tokenizer, docs; the BF16 text encoder is skipped for disk) and `/mnt/fast-ai/llm-models/minimax-h3-comfy`
(INT8 ConvRot denoiser and text encoder, fp16/fp32 VAEs). Script: `/mnt/fast-ai/llm-models/minimax-h3-download.sh`.

Detailed stand-up plan: [notes/2026-09-17-pipeline-plan.md](notes/2026-09-17-pipeline-plan.md).

## Next steps (not started)

1. Read the official `scripts/` and `model_index.json` for the pipeline (schedulers, sampling steps, guidance; H3 is
   distilled and CFG-free).
2. Stand up the PyTorch XPU pipeline from the LTX lane's pattern: text encoder pass, denoiser split over two cards,
   VAE decode; first with the BF16 denoiser offloaded (slow, correctness reference), then INT8 ConvRot.
3. Measure: a fixed prompt set, exact repeat determinism, time per clip, and INT8 vs BF16 reference frames.
