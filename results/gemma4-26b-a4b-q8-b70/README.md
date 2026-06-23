# Gemma 4 26B A4B Q8 on Intel B70

Status: **active lane, no validated baseline yet**.

This lane replaces the closed Qwen3.6 35B TP4 effort. The target architecture is
different on purpose: run **one complete Gemma 4 26B A4B replica per B70** and
avoid tensor-parallel PCIe overhead. The host has four B70s, so the research
workflow should normally run four independent single-GPU attempts in parallel.

## Target

- Model family: Gemma 4 26B A4B instruction tuned.
- Primary quality target: no lower than INT8-equivalent weights. Do **not** use
  INT4 AutoRound as the default lane.
- Primary runtime target: single-session decode rate on short/small-context
  prompts first, then 32K-context viability after the Q8 fit is proven.
- Preferred first artifact:
  `unsloth/gemma-4-26B-A4B-it-GGUF`,
  `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf` (27.6 GB).
- First runtime lane: llama.cpp SYCL/Level Zero, one process per GPU.
- Secondary runtime lane: vLLM/XPU with `google/gemma-4-26B-A4B-it` and
  `--quantization int8_per_channel_weight_only`, one process per GPU.
- Nice-to-have after text baseline: image input / multimodal smoke.

## Why This Shape

The model is MoE with about 25.2B total parameters and about 3.8B active
parameters, so a full Q8 GGUF copy should fit on a 32 GB B70 with limited KV
headroom. Running four replicas avoids the Qwen-style TP4 PCIe/collective cost
and lets four experiments run at once.

External references:

- Unsloth GGUF repo and Q8 file list:
  <https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/tree/main>
- Unsloth model card and llama.cpp / vLLM / Ollama entry points:
  <https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF>
- vLLM Gemma 4 recipe, including 26B A4B single-GPU and int8-per-channel notes:
  <https://docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html>
- vLLM Gemma 4 MoE DP issue recommending separate DP=1 instances:
  <https://github.com/vllm-project/vllm/issues/38999>
- LocalMaxxing Gemma 4 26B A4B leaderboard:
  <https://www.localmaxxing.com/en/models/google/gemma-4-26B-A4B-it>
  (useful for targets, but current top public rows include lower-precision
  modes such as MXFP4/Q4 and are not direct Q8-quality comparisons).

## Current Local State

- Four B70s are visible as Level Zero devices `level_zero:0..3`.
- llama.cpp upstream was cloned to `/home/steve/src/llama.cpp` and built with
  SYCL/Level Zero at commit `dec5ca557`; server binaries are under
  `/home/steve/src/llama.cpp/build-sycl-b70/bin/`.
- There is enough disk for the Q8 GGUF; `/mnt/fast-ai` had about 353 GB free at
  lane start.
- The Q8 GGUF download is in progress under
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/`.
- The dirty `/home/steve/src/vllm` Qwen worktree should not be treated as the
  baseline for this lane.

## First Milestones

1. Build upstream llama.cpp with SYCL/Level Zero.
2. Download the Q8 GGUF to
   `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/`.
3. Launch one `llama-server` replica on a single B70 at `CTX_SIZE=8192` and
   establish a valid text-only baseline before attempting 32K.
4. Launch four replicas on ports `18260..18263` and run four independent
   experiments/benchmarks in parallel.
5. Compare against a vLLM/XPU int8-per-channel single-GPU baseline only after
   llama.cpp has a stable text baseline.

## Result Table

| Date | Runtime | GPU Layout | Precision | Context | Status | Output tok/s | Evidence |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| 2026-06-23 | llama.cpp SYCL setup | 1 replica / B70 | UD-Q8_K_XL GGUF | 8K first, 32K target | model download | n/a | [lane start note](../../notes/2026-06-23-gemma4-26b-a4b-q8-b70-lane-start.md) |

## Linked Files

- [Reproduction commands](reproduce.md)
- [Validity gates](validity-gates.md)
- [Runtime plan](runtime-plan.md)
- [Research plan and experiment queue](research-plan.md)
- [Model and runtime options](model-options.md)
- [LocalMaxxing targets and submission packet](localmaxxing-and-targets.md)
- [Bugs and failed paths](bugs-failed-paths.md)
- [Active experiment folder](../../experiments/gemma4-26b-a4b-q8-b70/README.md)
