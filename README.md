# Unofficial Intel XPU Optimization Lab

Recipes, benchmarks and a home-built inference engine for running large AI
models locally on **Intel Arc Pro B70** graphics cards (and other Intel
Arc/XPU hardware). The public site is **[neural.download](https://neural.download/)**;
this repository holds the source, recipes and evidence behind every number on it.

This is community research, not a supported product, and it is not affiliated
with Intel. Commands, patches and results are provided under the
[LICENSE](LICENSE) with the risks described in [DISCLAIMER.md](DISCLAIMER.md).

## Current focus: our own B70 engine

We are building a model-specific inference engine for the B70 in SYCL/C++.
It runs [SC117's IQ3_S quantization](https://huggingface.co/SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF)
of **Qwen3.8 Flash-Next** (125B total parameters, about 6B active per token)
with 32-bit activations, recurrent state and attention cache, plus the
official FP8 draft model for speculative decoding. Every speed change must
leave outputs and engine state bit-identical.

Latest results (October 26–29, 2026). These are lab observations with linked
receipts, not certified records:

| Setup | Result | Evidence |
| --- | --- | --- |
| 4 B70s, each pipeline stage split exactly across two cards, 64K context | **78.29–78.62 tok/s** on fresh servers (2 cards: 66.42), identical outputs | [result](experiments/own-xpu-runtime/research/tp/fault-ladder-2026-10-29/RESULT.md) |
| Same 4-card split at 128K context, 121,854-token prompt | First token after 355 s, then **76 tok/s**; outputs equal the 262K layout | [result](experiments/own-xpu-runtime/research/tp/ctx131072-2026-10-29/RESULT.md) |
| 2 B70s, chat service, 64K context | **66.21 tok/s** decode on 12 cold prompts | [suite receipt](experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/d-mtp-fp8/suite/f32-suite-51f32b2655cc-ctx65536-split23.json) |
| 3 target B70s + 1 draft B70, 64K context | **58.57 tok/s**; all 5,965 outputs match CPU-checked references | [paired summary](experiments/own-xpu-runtime/research/pp4-review-2026-10-28/dedicated-depth2-gate/full12-r2-paired-summary.json) |
| Same layout, 262K context, 121,854-token prompt | First token after 250.8 s, then 48.5 tok/s | [long-prompt summary](experiments/own-xpu-runtime/research/pp4-review-2026-10-28/equal16-topology-screen/equal16-r1-evidence/summary.json) |

Splitting each layer exactly across two cards made four cards the fastest
setup for one conversation; a separate four-card layout holds a 262K context.

- Overview: [the own engine on neural.download](https://neural.download/own-runtime.html)
- Try it: [October 28 SC117 research recipe](repro/sc117-iq3s-b70-research-draft-20261028/README.md), its [results](repro/sc117-iq3s-b70-research-draft-20261028/RESULTS.md)
  and [how the engine works](repro/sc117-iq3s-b70-research-draft-20261028/EXPLAINER.md). It is an expert recipe; there is no
  one-command launcher or clean-host installer yet.
- Source: [engine and build instructions](experiments/own-xpu-runtime/engine/);
  day-to-day progress is in [CURRENT.md](CURRENT.md).
- The earlier own-engine recipes for Unsloth's UD-IQ3_XXS
  ([one card](repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/README.md),
  [two cards](repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/README.md)) use a different
  quantization and 16-bit recurrent state; treat them as a separate model line.

## What to run on a B70

The [neural.download home page](https://neural.download/#featured) picks one
setup per job by card count, with every number linked to its receipt:

- **1 card:** [Qwen3.8 27B AutoRound INT4](https://neural.download/models/qwen38-27b-autoround-int4-b70.html) for everyday chat and code,
  [Qwen3.8 27B FP8](https://neural.download/models/qwen38-27b-fp8-vllm-tp1-b70.html) for longer documents,
  [Gemma 4 26B-A4B Q8](https://neural.download/models/gemma4-26b-a4b-q8-b70-125tps-20260701.html) for fast replies.
- **2 cards:** [Qwen3.8 27B FP8 shared chat](https://neural.download/models/qwen38-27b-fp8-vllm-tp2-asrock-b70.html) for many users;
  [MiniMax-H3](https://neural.download/models/minimax-h3-pruned-bf16-tp2-b70-20261004.html) for video clips with audio.
- **4 cards:** [Qwen3.8 Flash-Next FP8](https://neural.download/models/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913.html) (certified lossless),
  [Laguna S 2.1](https://neural.download/models/laguna-s-2.1-int4-b70-125tps-20260731.html) for code,
  [LTX 2.5](https://neural.download/models/ltx25-continuation-stream-b70-145f-20261010.html) for a continuing video stream, and
  [SC117 on our own engine](https://neural.download/models/sc117-iq3s-b70-research-draft-20261028.html) for a 262K context.

Browse every package in the [recipe library](https://neural.download/guides.html).

## Who This Is For

- Local AI users who want reproducible Intel Arc/B-series commands, patches and
  benchmark recipes.
- Anyone deciding whether Intel Arc/B-series hardware is worth it for local
  inference, and wanting to see the state of support.
- Optimization agents and contributors who need a map of current work,
  archived lessons, and validity rules.
- Upstream vLLM, llama.cpp, oneAPI, SYCL, and Intel/XPU developers looking for
  concrete repros and failure signatures.

## Start Here

| Need | Entry Point |
| --- | --- |
| See the current own-engine work | [Own engine on neural.download](https://neural.download/own-runtime.html), [SC117 recipe](repro/sc117-iq3s-b70-research-draft-20261028/README.md) and [engine source](experiments/own-xpu-runtime/engine/) |
| Understand the repo structure | [Docs index](docs/README.md) |
| Find an experiment, retained patch, or cleanup decision | [Experiment index](experiments/README.md), [patch catalogs](patches/README.md), and [cleanup audit](audits/repository-cleanup/README.md) |
| See every active, paused, and archived model lane | [Model effort index](docs/model-effort-index.md) |
| Find a tested result or reproduction artifact | [Results index](results/README.md), [classified reproduction catalog](repro/README.md), and [certification standard](docs/reproduction-guide-certification.md) |
| Try a packaged candidate | Browse the [model guide library](guides.html) or its [machine-readable package catalog](packages/catalog.json); each package states its certification status |
| Start optimizing a new model | [Model optimization guide](docs/model-optimization-guide.md) |
| See or prepare the next model downloads | [Model intake queue](model-intake/README.md) |
| Follow the Docker and Windows packaging path | [Distribution and packaging roadmap](docs/model-distribution-and-packaging-roadmap.md) |
| Plan PCIe slots, risers, or external GPUs | [PCIe topology and local-LLM inference](docs/pcie-topology-and-llm-inference.md) |
| Diagnose freezes, resets, or silent data corruption | [Host stability and fault diagnosis](docs/host-stability-and-fault-diagnosis.md) |
| Compare expected model performance | [Performance scoreboard](results/scoreboard.md) |
| Contribute a result, patch, or correction | [Contribution guide](CONTRIBUTING.md) and [verification policy](docs/contribution-verification.md) |
| Review or validate incoming work | [Manager playbook](MANAGER.md) |
| Reuse the best research prompts/workflows | [Research workflow playbook](docs/research-workflow-playbook.md) |
| Find recorded host state, restrictions, and active work | [Current workspace state](CURRENT.md) (detailed lab log, newest first) |
| Find retained recipes and their limits | [Current reproducibility map](docs/current-reproducibility-map.md) |
| Submit or audit LocalMaxxing records | [LocalMaxxing submissions](docs/localmaxxing.md) |
| Handle local ops, secrets, sudo, and cross-agent delegation | [Local ops](docs/local-ops.md) |
| Review Intel-facing issues and asks | [Feedback for Intel](docs/feedback-for-intel.md) |
| Read older front-page results and model boards | [Lab results history](docs/lab-results-history.md) |

## Package catalog

Generated from the package manifests by `tools/sync-public-result-summary.py`;
do not edit it by hand. It is a synchronization view, not a ranking:
workloads, context lengths, card counts, quantization and speculative-decoding
modes differ. Each detail page states the exact measurement scope and evidence.

<!-- BEGIN GENERATED PUBLIC PACKAGE HEADLINES -->
| Model and deployment | Package status | Measured headline | Exact guide |
| --- | --- | ---: | --- |
| **[Qwen3.5 4B W4A16 with its own MTP head on one or two Intel Arc Pro B70](models/qwen35-4b-w4a16-b70.html)**<br>1&times; B70 · W4A16 (compressed-tensors INT4 weights, FP16 activations) · vLLM XPU | `candidate` · clean-host replay pending | **`191.727574 tok/s`**<br>Best qualified single-user record: MTP3, 67,248-row draft shortlist; fresh servers 191.87 / 191.58 | [reproduction guide](repro/qwen35-4b-w4a16-b70/README.md) |
| **[LFM2.5 24B A2B Q8_0 on one Intel Arc Pro B70 (exact fast path)](models/lfm25-24b-a2b-q8-b70.html)**<br>1&times; B70 · Q8_0 · llama.cpp SYCL + lab patch | `candidate` · clean-host replay pending | **`137.61891 tok/s`**<br>strict class-balanced decode | [reproduction guide](repro/lfm25-24b-a2b-q8-b70/README.md) |
| **[LFM2.5 2.6B Q8_0 on one Intel Arc Pro B70](models/lfm25-26b-q8-b70.html)**<br>1&times; B70 · Q8_0 · llama.cpp SYCL | `candidate` · clean-host replay pending | **`132.137457 tok/s`**<br>strict class-balanced decode | [reproduction guide](repro/lfm25-26b-q8-b70/README.md) |
| **[Laguna S 2.1 INT4 with DFlash on four Intel Arc Pro B70 cards](models/laguna-s-2.1-int4-b70-125tps-20260731.html)**<br>4&times; B70 · INT4 / BF16 KV · vLLM XPU | `candidate` · clean-host replay pending | **`125.461973 tok/s`**<br>conventional decode median | [reproduction guide](repro/laguna-s-2.1-int4-b70-125tps-20260731/README.md) |
| **[Qwen3.5 9B W4A16 with its own MTP head on one or two Intel Arc Pro B70](models/qwen35-9b-w4a16-b70.html)**<br>1&times; B70 · W4A16 (compressed-tensors INT4 weights, FP16 activations) · vLLM XPU | `candidate` · clean-host replay pending | **`124.084255 tok/s`**<br>Best qualified single-user record: MTP3, 67,248-row draft shortlist; fresh servers 124.04 / 124.13 | [reproduction guide](repro/qwen35-9b-w4a16-b70/README.md) |
| **[Gemma 4 26B A4B UD-Q8_K_XL on one Intel Arc Pro B70](models/gemma4-26b-a4b-q8-b70-125tps-20260701.html)**<br>1&times; B70 · UD-Q8_K_XL + Q4_0 MTP · llama.cpp SYCL | `candidate` · clean-host replay pending | **`122.160357 tok/s`**<br>decode (MTP-assisted) | [reproduction guide](repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md) |
| **[Qwen3.8 27B AutoRound INT4, fixed-K batch-invariant profile, on two Intel Arc Pro B70 cards](models/qwen38-27b-autoround-int4-b70.html)**<br>2&times; B70 · AutoRound INT4 W4A16 (group 128, symmetric) · vLLM XPU | `candidate` · clean-host replay pending | **`117.528083 tok/s`**<br>Best qualified TP2 record: MTP4 with the 67k draft shortlist (R299 / R294b) | [reproduction guide](repro/qwen38-27b-autoround-int4-b70/README.md) |
| **[Muse-Glimmer 30B Q8/WOQ with DFlash on four Intel Arc Pro B70 cards](models/muse-glimmer-30b-q8-woq-b70-100tps-20260813.html)**<br>4&times; B70 · UD-Q8_K_XL / BF16 draft · llama.cpp SYCL | `candidate` · clean-host replay pending | **`100.3685 tok/s`**<br>pooled canonical mean | [reproduction guide](repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md) |
| **[Qwen3.5 9B FP8-dynamic with its own MTP head on one Intel Arc Pro B70](models/qwen35-9b-fp8-b70.html)**<br>1&times; B70 · FP8-dynamic (compressed-tensors, per-channel FP8 weights, dynamic activations) · vLLM XPU | `candidate` · clean-host replay pending | **`98.139 tok/s`**<br>MTP depth 3 with the draft-only INT4 lm_head, one card, strict completions suite (center of two fresh servers, 98.251 / 98.027) | [reproduction guide](repro/qwen35-9b-fp8-b70/README.md) |
| **[Qwen3.8 27B official FP8 on two Intel Arc Pro B70 cards](models/qwen38-27b-fp8-vllm-tp2-asrock-b70.html)**<br>2&times; B70 · FP8 · vLLM XPU | `candidate` · clean-host replay pending | **`90.309841 tok/s`**<br>Historical writing speed · MTP depth 5 · two cards | [reproduction guide](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md) |
| **[MiniMax M2.7 AutoRound INT4 on four Intel Arc Pro B70 cards](models/minimax-m27-b70-89tps-20260520.html)**<br>4&times; B70 · AutoRound W4A16 INT4 · vLLM XPU + llm-scaler | `candidate` · clean-host replay pending | **`89.314195 tok/s`**<br>mean output throughput | [reproduction guide](repro/minimax-m27-b70-89tps-20260520/README.md) |
| **[Qwen3.8 27B Q4_K_M + MTP2 on two Intel Arc Pro B70 cards](models/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70.html)**<br>2&times; B70 · Q4_K_M target + Q4_0 MTP draft / F16 KV · llama.cpp SYCL | `candidate` · clean-host replay pending | **`64.237301 tok/s`**<br>strict varied-prompt decode | [reproduction guide](repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/README.md) |
| **[Qwen3.8 27B official FP8 on one Intel Arc Pro B70](models/qwen38-27b-fp8-vllm-tp1-b70.html)**<br>1&times; B70 · FP8 · vLLM XPU | `candidate` · clean-host replay pending | **`54.036484 tok/s`**<br>Writing speed · MTP depth 5 · one card | [reproduction guide](repro/qwen38-27b-fp8-vllm-tp1-b70/README.md) |
| **[Qwen3.8 27B Q4_K_M on two Intel Arc Pro B70 cards](models/qwen38-27b-q4km-tp2-asrock-b70.html)**<br>2&times; B70 · Q4_K_M / F16 KV · llama.cpp SYCL | `candidate` · clean-host replay pending | **`49.717503 tok/s`**<br>conventional decode median | [reproduction guide](repro/qwen38-27b-q4km-tp2-asrock-b70/README.md) |
| **[Qwen3.8 Flash-Next FP8 with lossless MTP1 and the GDN verifier rows in the kernel extension's exact serial mode, on four Intel Arc Pro B70 cards](models/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913.html)**<br>4&times; B70 · FP8 block-128 weights / BF16 KV · vLLM XPU | `candidate` · clean-host replay pending | **`46.85425 tok/s`**<br>class-balanced decode median | [reproduction guide](repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md) |
| **[Qwen3.8 27B Q4_K_M + MTP2 on one Intel Arc Pro B70](models/qwen38-27b-q4km-mtp2-tp1-b70.html)**<br>1&times; B70 · Q4_K_M target + Q4_0 MTP draft · llama.cpp SYCL | `candidate` · clean-host replay pending | **`42.636988 tok/s`**<br>strict varied-prompt decode | [reproduction guide](repro/qwen38-27b-q4km-mtp2-tp1-b70/README.md) |
| **[Qwen3.8 Flash-Next FP8 with lossless MTP1, never-routed experts host-placed and both reference Triton kernels restored, on four Intel Arc Pro B70 cards](models/qwen38-flash-next-fp8-tp4-mtp1-qsafused-b70-38tps-20260907.html)**<br>4&times; B70 · FP8 block-128 weights / BF16 KV · vLLM XPU | `candidate` · clean-host replay pending | **`37.825654 tok/s`**<br>class-balanced decode median | [reproduction guide](repro/qwen38-flash-next-fp8-tp4-mtp1-qsafused-b70-38tps-20260907/README.md) |
| **[Qwen3.8 27B Q8_0 + MTP2 on one Intel Arc Pro B70](models/qwen38-27b-q8-q4mtp-mtp2-tp1-b70.html)**<br>1&times; B70 · Q8_0 target + Q4_0 MTP draft · llama.cpp SYCL | `candidate` · clean-host replay pending | **`37.062028 tok/s`**<br>strict varied-prompt decode | [reproduction guide](repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/README.md) |
| **[Qwen3.8 Flash-Next FP8 with lossless MTP1, never-routed experts host-placed and the Triton hyper-connection glue on four Intel Arc Pro B70 cards](models/qwen38-flash-next-fp8-tp4-mtp1-hctriton-b70-37tps-20260907.html)**<br>4&times; B70 · FP8 block-128 weights / BF16 KV · vLLM XPU | `candidate` · clean-host replay pending | **`37.045844 tok/s`**<br>class-balanced decode median | [reproduction guide](repro/qwen38-flash-next-fp8-tp4-mtp1-hctriton-b70-37tps-20260907/README.md) |
| **[Qwen3.8 27B Q8_0 on two Intel Arc Pro B70 cards](models/qwen38-27b-q8-tp2-asrock-b70.html)**<br>2&times; B70 · Q8_0 / F16 KV · llama.cpp SYCL | `candidate` · clean-host replay pending | **`36.726447 tok/s`**<br>strict varied-prompt decode | [reproduction guide](repro/qwen38-27b-q8-tp2-asrock-b70/README.md) |
| **[Qwen3.8 Flash-Next FP8 with no speculation, never-routed experts host-placed, both reference Triton kernels restored and the W13 MoE tile at the base width, on four Intel Arc Pro B70 cards](models/qwen38-flash-next-fp8-tp4-mtp0-w13n64-b70-34tps-20260908.html)**<br>4&times; B70 · FP8 block-128 weights / BF16 KV · vLLM XPU | `candidate` · clean-host replay pending | **`34.495292 tok/s`**<br>class-balanced decode median | [reproduction guide](repro/qwen38-flash-next-fp8-tp4-mtp0-w13n64-b70-34tps-20260908/README.md) |
| **[Qwen3.8 Flash-Next FP8 with lossless MTP1 and never-routed experts host-placed on four Intel Arc Pro B70 cards](models/qwen38-flash-next-fp8-tp4-mtp1-placement-b70-32tps-20260906.html)**<br>4&times; B70 · FP8 block-128 weights / BF16 KV · vLLM XPU | `candidate` · clean-host replay pending | **`31.929484 tok/s`**<br>class-balanced decode median | [reproduction guide](repro/qwen38-flash-next-fp8-tp4-mtp1-placement-b70-32tps-20260906/README.md) |
| **[Qwen3.8 27B Q4_K_M on one Intel Arc Pro B70](models/qwen38-27b-q4km-tp1-b70.html)**<br>1&times; B70 · Q4_K_M · llama.cpp SYCL | `candidate` · clean-host replay pending | **`27.825726 tok/s`**<br>decode | [reproduction guide](repro/qwen38-27b-q4km-tp1-b70/README.md) |
| **[Qwen3.8 Flash-Next FP8 with lossless MTP1 on four Intel Arc Pro B70 cards](models/qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905.html)**<br>4&times; B70 · FP8 block-128 weights / BF16 KV · vLLM XPU | `candidate` · clean-host replay pending | **`27.048435 tok/s`**<br>class-balanced decode median | [reproduction guide](repro/qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905/README.md) |
| **[Qwen3.8 27B 256K + vision + MTP draft on one Intel Arc Pro B70](models/qwen38-27b-256k-vision-mtp-b70.html)**<br>1&times; B70 · UD-Q5_K_S (shipped) / UD-Q4_K_XL (alternative) · llama.cpp SYCL | `candidate` · clean-host replay pending | **`26.668277 tok/s`**<br>decode (MTP-assisted, full package resident) | [reproduction guide](repro/qwen38-27b-256k-vision-mtp-b70/README.md) |
| **[Qwen3.8 27B Q8_0 on one Intel Arc Pro B70](models/qwen38-27b-q8-tp1-b70.html)**<br>1&times; B70 · Q8_0 · llama.cpp SYCL | `candidate` · clean-host replay pending | **`19.61924 tok/s`**<br>strict varied-prompt decode | [reproduction guide](repro/qwen38-27b-q8-tp1-b70/README.md) |
| **[LTX 2.5 continuous video on four B70 cards](models/ltx25-continuation-stream-b70-145f-20261010.html)**<br>4&times; B70 · BF16 distilled weights; F32 output checks · ComfyUI / PyTorch XPU | `candidate` · clean-host replay pending | **strict headline pending**<br>Strict headline pending: scoped continuation timing only; seam/audio acceptance, sustained performance and independent replay remain open. | [reproduction guide](repro/ltx25-continuation-stream-b70-145f-20261010/README.md) |
| **[MiniMax-H3 video with audio on two B70 cards](models/minimax-h3-pruned-bf16-tp2-b70-20261004.html)**<br>2&times; B70 · Comfy-Org pruned BF16 denoiser + INT8 ConvRot encoder · Native diffusers / PyTorch XPU | `candidate` · clean-host replay pending | **strict headline pending**<br>Owner-approved measured batch; strict headline certification pending: baseline raw receipts and independent full-suite repeat are absent. | [reproduction guide](repro/minimax-h3-pruned-bf16-tp2-b70-20261004/README.md) |
| **[Nemotron 3.5 Lightning 30B-A3B UD-Q4_K_M on one Intel Arc Pro B70](models/nemotron-35-lightning-30b-a3b-b70.html)**<br>1&times; B70 · UD-Q4_K_M · llama.cpp SYCL | `candidate` · clean-host replay pending | **strict headline pending**<br>Historical August22 raw suites, canaries and server logs are now imported and hash-bound. The 72.169452/72.035976 tok/s text-delta observations remain non-headline: native-token-ID quality/determinism replay is incomplete. October19 replay was interrupted and owner-deferred; no qualified new result. | [reproduction guide](repro/nemotron-35-lightning-30b-a3b-b70/README.md) |
| **[Ornith 1.5 35B-A3B Q4_K_M on one Intel Arc Pro B70](models/ornith-15-35b-a3b-q4km-b70.html)**<br>1&times; B70 · Q4_K_M · llama.cpp SYCL | `candidate` · clean-host replay pending | **strict headline pending**<br>The 131.460231 tok/s two-server observation and matched patch A/B evidence remain valid scoped measurements, but the runtime produced 0/12 identical complete natural-response hashes across fresh stock servers. Keep the mechanism and context evidence; require a stable, registered cross-server oracle before assigning a strict package headline. | [reproduction guide](repro/ornith-15-35b-a3b-q4km-b70/README.md) |
| **[Ornith 1.5 9B Q8_0 on one Intel Arc Pro B70](models/ornith-15-9b-q8-b70.html)**<br>1&times; B70 · Q8_0 · llama.cpp SYCL | `candidate` · clean-host replay pending | **strict headline withheld**<br>Strict headline withheld after output-gate failure. Two complete fresh-server, cache-zero, 12-prompt/six-class attempts measured 49.593582 and 49.515869 tok/s and passed both objective-canary batteries, but complete token arrays matched only 8/12 across servers. | [reproduction guide](repro/ornith-15-9b-q8-b70/README.md) |
| **[Qwen3.8 Flash-Next UD-IQ3_XXS — own runtime, one GPU](models/qwen38-flash-next-iq3xxs-ownrt-tp1-b70.html)**<br>1&times; B70 · UD-IQ3_XXS · Own Xe runtime (packet58aj / packet165c) | `candidate` · clean-host replay pending | **strict headline pending**<br>Historical 128-token record: 37.595605 tok/s; separate full-512 timings below. Oracle parity uses BF16 recurrent state. Reference-FP32 fidelity and no-added-loss qualification remain unestablished. | [reproduction guide](repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/README.md) |
| **[Qwen3.8 Flash-Next UD-IQ3_XXS — own runtime, two GPUs](models/qwen38-flash-next-iq3xxs-ownrt-tp2-b70.html)**<br>2&times; B70 · UD-IQ3_XXS · Own Xe runtime (bundle 8 / packet165) | `candidate` · clean-host replay pending | **strict headline pending**<br>Historical 128-token record: 63.611824 tok/s; separate full-512 timings below. Oracle parity uses BF16 recurrent state. Reference-FP32 fidelity and no-added-loss qualification remain unestablished. | [reproduction guide](repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/README.md) |
| **[SC117 Flash-Next IQ3_S — dedicated draft, three or four B70 cards](models/sc117-iq3s-b70-research-draft-20261028.html)**<br>4&times; B70 · IQ3_S mixed GSQ-RCO · Own Xe/SYCL runtime; BMG-G31 AOT | `candidate` · clean-host replay pending | **strict headline pending**<br>Strict certified headline and context sweep pending. The later binary 9599b0 saved-continuation CPU qualification and the 2+1 gate are separate from the older frozen-source recipe; see the latest research results. | [reproduction guide](repro/sc117-iq3s-b70-research-draft-20261028/README.md) |
<!-- END GENERATED PUBLIC PACKAGE HEADLINES -->

## How The Repo Is Organized

The repo is organized around model lanes, not one-off leaderboard
rows. A serious lane should leave behind:

- `results/<model>-<quant>-<hardware>/`: promoted or closed-out result packet,
  validity gates, best commands, invalid fast lanes, and lessons.
- `repro/<model>-.../`: classified reproduction artifacts, ranging from
  portable candidates to originating-host lab replays and archived records;
  the catalog, not the directory name, states portability.
- `packages/<model>-.../`: user-facing, machine-readable front doors over
  exact in-repository guides, commands, dependencies, and evidence.
- `experiments/<model>-.../`: active research lanes that are not production
  recipes yet.
- `notes/`: chronological lab notebook entries, including negative results and
  postmortems.
- `patches/`: patch snapshots and source/config deltas, including failed
  experiments worth preserving.
- `data/`: compact structured benchmark records, payloads, responses, and logs.
- `scripts/`: reusable harnesses, analyzers, launchers, and submission helpers.
- `model-intake/`: revision-pinned candidate catalog, storage budget, and the
  boundary between discovery, download, validation, and promotion.
- `community/<contributor>-...`: runnable work contributed from outside the
  reference lab, with explicit evidence status and validation history.
- `community/field-reports/`: unverified measurements and observations from
  community systems, kept separate from recipes, patches, validation assets,
  and promoted results. See [`community/README.md`](community/README.md).

The point is to make model switching cheap. Gemma, Qwen, MiniMax, and future
lanes should all share validation discipline, result-packet shape, and reusable
kernel/runtime lessons without dragging stale generated builds or huge artifacts
forward.

## Validity Rules For Speed Claims

Diagnostic runs are allowed and useful, but headline records require the
model-lane gate. For Gemma/Qwen-style fresh-response records, that means:

- fixed realistic prompt suite;
- each prompt run once as a cold response;
- `cached_tokens=0` for every request;
- no prompt/KV cache reuse, context checkpoints, response reuse, warmed
  repeated prompts, or n-gram/history acceleration;
- target model and quantization unchanged;
- speculative decoding/MTP allowed only when accepted tokens are verified by
  the declared target model;
- primary metric is the median conventional rate across the 99 inter-token
  intervals between timestamps 1 and 100 after TTFT, with p10, mean, TTFT,
  wall-clock full-output throughput, full-output after-TTFT throughput, hashes,
  runtime identity, env vars, flags, and logs. Historical 100-event/99-interval
  compatibility fields must be labeled as such.

Synthetic, repeated, warmed, cached, or history-assisted rows stay diagnostic
unless revalidated by the lane's promotion gate. This matters because several
very fast historical rows were useful optimization clues but not real-world
fresh-response claims.

## Hardware

The main lab host has **four Intel Arc Pro B70 32 GB cards** and 128 GiB of
system RAM, of which about 96 GiB is available to model processes. A second
host has **two ASRock Arc Pro B70 32 GB cards** with PCIe 5.0 x16 links but
only about 15 GiB of system RAM, so it suits models that stream little from
host memory (the MiniMax-H3 video recipe was measured there). Card count and
host identity are part of every result; GPU count alone is not a safety
signal.

Results from Intel Arc Pro B50, B60, B65 and B70 owners are welcome, as are
observations from other Intel Arc and XPU systems. A B70 rerun verifies what a
patch does on B70; it does not certify a score on hardware the maintainers do
not have, so hardware and verification status stay explicit in every result.
For B65 buyers, see the [B65 field report](community/field-reports/boyter/arc-pro-b65-qwen38/README.md)
(unverified community numbers; B65 has 20 Xe cores versus 32 on the B70, with
the same 32 GB and 608 GB/s memory).

Steve Seguin maintains this repo and posts build notes at
<https://x.com/xyster>.

<img height="600" alt="Four Intel Arc Pro B70 cards in the lab host" src="https://github.com/user-attachments/assets/e6ce5633-17ff-4a73-924d-31dcbc913ede" />

## How To Contribute

This remains primarily a working optimization lab, but careful outside
contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and
the [manual verification policy](docs/contribution-verification.md). No result
needs to be a record to be useful.

Useful contributions include:

- reproducing a result on another Intel/XPU stack and sharing exact versions;
- testing a failed lane after a driver, PyTorch XPU, vLLM, llama.cpp, or oneAPI
  update;
- turning local patches into clean upstream issues or PRs;
- adding quality canaries for new model families;
- sharing high-signal failure logs with model, quantization, graph mode, and
  hardware identity intact;
- providing temporary access to larger Intel hardware for models that do not
  fit cleanly on 32 GB cards.

When opening an issue or discussion, include GPU, OS, model, quantization,
runtime, exact command, benchmark shape, quality gate, result JSON/log paths,
and what changed from the closest known-good run.

## Reusable Optimization Lessons

The durable value of this lab is not only its fastest rows. Start with the
[cross-model pattern catalog](docs/research-workflow-playbook.md#cross-model-patterns-worth-reusing)
for evidence-linked strategies that transfer across model lanes, and the
[model optimization guide](docs/model-optimization-guide.md) for the
identity, quality, A/B, variance, and negative-result process used to test them.
Model-specific packets retain the commands and caveats behind each lesson.

## History

- [Lab results history](docs/lab-results-history.md): the README's former
  results section, research entry points and the Qwen3.8/Qwen3.6 27B model
  boards, moved verbatim on October 28, 2026.
- [Historical B70 archive](notes/2026-07-11-readme-historical-b70-archive.md):
  the original long-form chronology and file inventory up to July 11, 2026.
- [Model effort index](docs/model-effort-index.md) and
  [results index](results/README.md): every active, paused and closed lane.
