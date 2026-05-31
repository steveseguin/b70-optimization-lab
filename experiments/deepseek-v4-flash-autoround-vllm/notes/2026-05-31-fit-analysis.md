# 2026-05-31 Fit Analysis

## Summary

`Intel/DeepSeek-V4-Flash-W4A16-AutoRound` is an INT4/W4A16 checkpoint, but it
does not cleanly fit on 4x 32 GB B70s with a normal TP4 vLLM plan.

Direct Hugging Face repo-tree file sizes:

- DeepSeek V4 Flash W4A16 AutoRound safetensors: `152.95 GB` decimal /
  `142.44 GiB`
- 4-way equal split floor: `38.24 GB` decimal / `35.61 GiB` per GPU
- B70 usable VRAM target for a stable vLLM run is below 32 GB after allocator,
  KV cache, graph/compile buffers, and scratch.

So TP4 is over budget before KV cache and runtime overhead.

## Why INT4 Is Still Large

The model is MoE-heavy. INT4 reduces each logical expert weight, but there are
many routed expert weights:

- 43 layers
- 256 routed experts
- expert MLP dimensions roughly `4096 -> 2048 -> 4096`
- 6 experts active per token, but all experts still need to be resident or
  quickly accessible unless we build an offload/cache path.

The HF UI reports about 40B stored tensor elements, but packed `I32` qweights
encode multiple 4-bit values. The logical MoE weight count is much larger than
the UI element count suggests.

## What Would Fit

Likely clean options:

- 8x 32 GB GPUs, matching the upstream inference folder's MP8 expectation.
- 4x 48 GB or 4x 64 GB GPUs.
- A smaller/further-quantized checkpoint, likely around 3-bit or aggressive GGUF
  quantization.
- CPU/NVMe expert offload or paging, but this becomes a speed/latency research
  project and should not be compared to fully resident GPU runs without clear
  labeling.

## Candidate Alternatives

Measured direct repo-tree sizes on 2026-05-31:

| Model | Format | Size | Fit outlook on 4x B70 |
| --- | --- | ---: | --- |
| `Intel/DeepSeek-V4-Flash-W4A16-AutoRound` | safetensors AutoRound W4A16 | `142.44 GiB` | No clean TP4 fit |
| `RedHatAI/DeepSeek-V4-Flash-NVFP4-FP8` | safetensors NVFP4/FP8 | `152.96 GiB` | Worse for fit |
| `mlx-community/DeepSeek-V4-Flash-4bit` | MLX safetensors | `141.09 GiB` | Still too large, not vLLM/XPU target |
| `stepfun-ai/Step-3.7-Flash-NVFP4` | safetensors NVFP4/modelopt | `115.85 GiB` | Possible but tight; official card has TP4 vLLM recipe |
| `stepfun-ai/Step-3.7-Flash-GGUF` `IQ4_XS` | GGUF | `97.78 GiB` plus support files | Likely fits in llama.cpp, not vLLM |
| `stepfun-ai/Step-3.7-Flash-GGUF` `Q4_K_S` | GGUF | `103.84 GiB` plus support files | Likely fits in llama.cpp, not vLLM |
| `stepfun-ai/Step-3.7-Flash-GGUF` `IQ3_XXS` | GGUF | `70.56 GiB` plus support files | Best fit, quality unknown vs 4-bit |

## Revised Plan

If the target remains DeepSeek V4 AutoRound:

1. Still do dummy/no-weight vLLM construction work to learn the XPU blockers.
2. Do not expect full-resident TP4 to fit.
3. Evaluate expert offload/paging or further quantization only after the
   construction path is understood.
4. Treat any offloaded run as a separate performance class.

If the target is "largest useful model that can fit 4x B70 with vLLM":

1. Start a parallel Step 3.7 Flash NVFP4 track.
2. Use the official TP4/modelopt/fp8-KV recipe as the first attempt.
3. Expect B70/XPU-specific work because modelopt and NVFP4 support may be
   CUDA-oriented.

If the target is "fits now with less vLLM purity":

1. Test Step 3.7 Flash GGUF `IQ4_XS` or `Q4_K_S` in llama.cpp/SYCL.
2. Keep it separate from vLLM/AutoRound records.
