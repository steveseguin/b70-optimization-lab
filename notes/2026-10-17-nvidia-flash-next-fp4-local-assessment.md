# NVIDIA Qwen3.8-Flash-Next-FP4-Local: fit for the B70 lab (assessment, 2026-10-17)

This assessment used the Hugging Face API and the model card only. Nothing was downloaded.

## What the model is

- **Repo:** `nvidia/Qwen3.8-Flash-Next-FP4-Local`, revision `b9ce18a6…`; created 2026-10-08, updated 2026-10-15.
- **License:** NVIDIA Open Model Agreement, plus the Qwen Community License.
- **Size:** 21 safetensors shards, 102.26 GB (the card says about 96 GiB).
- **Older sibling:** `nvidia/Qwen3.8-Flash-Next-NVFP4` (2026-09-02, 132.73 GB).

**It is QAD, not a plain quantization.** Quantization-aware distillation from the BF16 teacher retrained the weights (500M tokens × 3 epochs), including the n-gram (PLE) tables. So it is a derived model with its own outputs. Under the lab's rules it would be a separate lane, lossless only against itself.

| Component | Format (config `quantized_layers`) | Approximate size |
|---|---|---|
| Routed experts, 48 layers × 512 (≈121B params) | NVFP4: E2M1 values, E4M3 scales per 16, FP32 global; scales in a new compressed "csf" encoding | ≈68 GB |
| PLE n-gram table (20M × 2560 ≈ 51B params, layer 2) | NVFP4 (`ple_embedding_dtype nvfp4`) | ≈29 GB |
| Attention and shared experts (438 layers) | MXFP8: E4M3 values, UE8M0 scales per 32 | ≈4-5 GB |
| MTP experts; lm_head and MTP attention/shared | MTP experts NVFP4 (W4A16); the rest unquantized | small |

The card reports GPQA Diamond 91.5% against 92.2% for BF16, and ToolEvalBench 88.7% against 89.4%.

**Runtime support:**

- It was validated only on NVIDIA Blackwell (one RTX PRO 6000 with PLE offload; DGX Spark).
- It needs community vLLM containers; upstream vLLM does not yet read the csf scales.
- There is no Intel XPU path. The B70 has no FP4 or FP8 matrix hardware, so weights must be dequantized to BF16 inside our own kernels.

## Against our IQ3 line

Unsloth UD-IQ3_XXS: 81.96 GB on disk. Our own runtime runs it on 2 cards, with the record at 39.42 tok/s.

| | IQ3_XXS (in use) | FP4-Local |
|---|---|---|
| Disk | 82.0 GB | 102.3 GB |
| Expert bits per weight | ≈3.06 | ≈4.5 |
| Quality vs BF16 | not measured here; 3-bit typically loses more | near BF16 per the NVIDIA card (QAD) |
| Weights vs the original | quantized only | quantized and **retrained** (QAD) |
| Source rule | Unsloth: trusted | NVIDIA: **not on the trusted list** (owner, Unsloth, Intel). Needs the owner's approval before download |
| B70 runtime today | our own runtime, 2 cards | none; needs NVFP4 + MXFP8 + csf-scale kernels in our runtime |

## Cards and host RAM on B70 (32 GB each)

- **PLE in host RAM** (as the NVIDIA card does on one GPU): about 73 GB stays on the cards.
  - **3 B70s minimum** (about 24 GB per card plus KV);
  - **4 B70s recommended** (about 18 GB per card, room for KV and long context).
  - 2 cards would need about 10+ GB of experts parked in host memory; workable but slower.
- **Host RAM:** about 27 GiB pinned for PLE, plus load staging. This host has about 118 GiB available, so it fits.
- **All 4 cards, no offload** would need everything (about 102 GB) on the cards. That leaves about 26 GB of total headroom: tight but possible.
- The certified FP8 line, by contrast, needs about 49 GB of experts in host RAM even on 4 cards. A full-VRAM FP4 line removes that offload entirely.

## Verdict

- **Technically a strong candidate for a 4-card lane.** Near-BF16 quality, it fits in VRAM, and it reads fewer bytes per token than FP8.
- **The catches:**
  1. The owner must approve the NVIDIA source, under the source rule.
  2. QAD makes it a different model from both FP8 and IQ3, so its records are separate and never compared as the same model.
  3. A new weight-format path in our own runtime: NVFP4 GEMV with E4M3 per-16 scales and the csf scale decode, MXFP8 projections, and a 3- or 4-card split. That is days of work.
- **No speed estimate is claimed.** The IQ3 runtime is overhead-bound, so bits per weight alone do not predict tok/s.
