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
| unsloth `MiniMax-H3-FP8.pt` / Comfy `fl2va_pruned_fp8_scaled` | 20-21 GB (**pruned** denoiser, 40 GB in BF16) | same | "pruned" removes about 40% of the denoiser; quality vs the full model is unmeasured here |
| unsloth GGUF `fl2va_pruned-Q8_0` | 20.0 GiB (pruned) | `qwen3vl_32b_minimax_h3-Q4_K_M` 17 GiB | stable-diffusion.cpp (SYCL backend exists); text encoder on CPU needs more than this host's 15 GiB RAM, so it would run on the second card |

The user's brief is best quality that fits comfortably, no quality loss by design: the candidate is the **full
denoiser at INT8 ConvRot (34 GB) split across the two cards**, with the INT8 text encoder run first on one card and
unloaded, and the fp16 video VAE (5.2 GB) plus audio VAE. The pruned builds are a fallback, not the plan, until their
quality is measured against the full one. The BF16 denoiser is kept as the reference/source (a BF16 reference run
needs the four-card host, 128 GiB).

## Downloaded to this host

`/mnt/fast-ai/llm-models/minimax-h3` (original: `transformer/`, `vae/`, `audio_vae/`, schedulers, processor,
tokenizer, docs; the BF16 text encoder is skipped for disk) and `/mnt/fast-ai/llm-models/minimax-h3-comfy`
(INT8 ConvRot denoiser and text encoder, fp16/fp32 VAEs). Script: `/mnt/fast-ai/llm-models/minimax-h3-download.sh`.

## Next steps (not started)

1. Read the official `scripts/` and `model_index.json` for the pipeline (schedulers, sampling steps, guidance; H3 is
   distilled and CFG-free).
2. Stand up the PyTorch XPU pipeline from the LTX lane's pattern: text encoder pass, denoiser split over two cards,
   VAE decode; first with the BF16 denoiser offloaded (slow, correctness reference), then INT8 ConvRot.
3. Measure: a fixed prompt set, exact repeat determinism, time per clip, and INT8 vs BF16 reference frames.
