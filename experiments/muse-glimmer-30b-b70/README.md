# Muse Glimmer 30B B70 Experiments

Active experiment lane opened 2026-08-10 for Meta Muse Glimmer 30B on Intel
Arc Pro B70. Operator directive: **maximum quality first (lossless or very
near lossless), then maximum speed.** Four B70s are available; the model may
run one replica per card only if quality survives, otherwise one replica per
two cards.

## Model Facts (from the official card, release 2026-08-10)

- Dense causal transformer + perception encoder, ~29.6B total params
  (~1.8B ViT-G/14 vision encoder), Apache 2.0.
- 52 layers, hidden 6656, FFN 19968 SwiGLU, GQA 32Q/2KV (16:1),
  head_dim 128, gated attention, final logit softcapping 20.0.
- Attention pattern [Local, Local, Local, Global], SWA window 2048; RoPE
  (theta 500k) on local layers only, global layers NoPE.
- Vocab 202,048; context 131,072+; controllable reasoning strength
  (low/medium/high/xhigh via system prompt); recommended sampling
  temperature 1.0, top_p 0.95, top_k 64.
- DFlash block-diffusion drafter: 5 layers, block size 16, GQA 32/8,
  reads target hidden features at layers {1,13,25,37,49}; exact target
  verification, so drafter quantization affects speed only, never output.
  Reference: 3.1x on RTX 5090 (74.9 -> 233.4 tok/s) with llama.cpp.

## Quality-First Fit Decision (2026-08-10)

Per-card usable envelope is ~32.6 GB (Gemma/Qwen precedent; MTP c2/32K
NO-GO at ~32,683 MiB).

| Arm | Artifact | Weights | Topology | Fit | Role |
| --- | --- | --- | --- | --- | --- |
| A | unsloth BF16 (2-part GGUF) | 55.7 GB | 1 model / 2 B70s | ~28 GB/card + KV/compute | lossless reference + verifier identity |
| B | unsloth UD-Q8_K_XL | 32.3 GB | 1 model / 2 B70s | ~16 GB/card, large KV headroom | near-lossless production candidate; must pass exact/quality gates vs Arm A |
| C | unsloth UD-Q6_K_XL | 26.3 GB | 1 model / 1 B70 | fits with drafter | single-card fallback only; below the quality bar unless gates prove otherwise |
| D | official kquant-dynamic | 19.7 GB | 1 B70 | comfortable | comparator vs Meta's published numbers (0.2% degradation claim) |

Single-card near-lossless is fit-blocked: Q8_0 (29.6 GB) + DFlash + buffers
~33.7 GB exceeds the envelope; UD-Q8_K_XL (32.3 GB) exceeds it alone. Do not
reopen without a source-level memory reduction. A text-only, no-spec Q8_0
single-card fit probe is allowed once as a documented GO/NO-GO.

KV is unusually cheap (2 KV heads; 39/52 layers SWA-2048): full-attention
KV at 131K is ~1.8 GB f16 total, so long context and multi-slot serving are
not memory-constrained in the 2-card arms.

## Assets

- `/mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/`:
  `Muse-Glimmer-30B-UD-Q8_K_XL.gguf`, `dflash-kquant.gguf`,
  `mmproj-Muse-Glimmer-30B-BF16.gguf`, `mmproj-kquant.gguf`,
  `sha256.txt`, `download-queue.urls`.
- `/mnt/usb-models/muse-glimmer-30b-extra/`:
  `Muse-Glimmer-30B-BF16-0000{1,2}-of-00002.gguf` (Arm A),
  `muse-glimmer-30B-kquant-dynamic.gguf`, `Muse-Glimmer-30B-UD-Q6_K_XL.gguf`.
  Copy Arm A to NVMe before formal timing runs if USB read speed contaminates
  load or paging behavior (decode should be VRAM-resident regardless).
- Runtime: `/home/steve/src/llama.cpp-muse-glimmer` at upstream `030ebb558`
  (clean master; Muse Glimmer support merged at `62bf73d25`, PR #26841),
  build `build-sycl-b70-aot-bmg-g31` (icx/icpx 2026.0, GGML_SYCL TARGET=INTEL,
  DEVICE_ARCH=bmg-g31, DNN=ON, GRAPH=ON), version 10358.
  Keep this tree clean-master until baselines are banked; patches go to
  `patches/muse-glimmer-30b-b70/` with source snapshots per lab standard.
- Upstream spec flags: `--spec-type draft-dflash --spec-draft-model
  dflash-kquant.gguf`; upstream also ships `draft-mtp`/`draft-eagle3`/
  `draft-dspark` for cross-checks.

## Exactness Status (2026-08-10, updates gate design)

Upstream master SYCL greedy decode is NOT run-deterministic on this stack
(no-spec included, conservative flags and fa-off included); outputs flip
among a small set of near-tie variants with no quality corruption. See
`sweeps/20260810-armB-pmin-depth-runtime-and-exactness.md`. Until a
deterministic identity is restored (lab precedent: Gemma/Qwen pinned builds
replay exactly), byte-exactness gates cannot pass and promotion is blocked.
Banked speed config for DFlash: `n_max=5, p_min=0.1` at 2.39x avg
(1.87x prose / 2.82x code / 2.48x json). Single-card discriminator probe
pending on the kquant-17gb artifact.

## Gates And Method

Inherit the Gemma/Qwen methodology wholesale: fixed cold realistic suite,
`cached_tokens=0`, no prompt/KV/response/history reuse, exact greedy replay
guards, same-window paired A/B near records, no-spec calibration, and
LocalMaxxing submission only after the full gate. Quality gate for Arm B
(and any quant below BF16): greedy exact-match and task-suite parity against
Arm A outputs on the same prompts, plus long-context retrieval canaries.
Speculative decoding must always verify with the serving target itself.

## First Sweep Matrix

After first serve smoke:

| GPUs | Purpose | First knobs |
| --- | --- | --- |
| 0+1 | Arm A BF16 baseline | `-sm layer` vs `-sm row`, no-spec vs DFlash `n_max` ladder (incl. 15/16 block alignment) |
| 2+3 | Arm B UD-Q8_K_XL | same ladder; then ubatch/prefill ladder; exact-match gate vs Arm A |
| any | fit probes | single-card Q8_0 text-only GO/NO-GO; mmproj BF16 vs kquant on vision canaries |

Record every sweep in `sweeps/` with quality status, not only speed.
