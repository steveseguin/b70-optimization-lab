# Qwen3.6 27B INT4 AutoRound on B70

This folder is the result packet for the `Intel/Qwen3.6-27B-int4-AutoRound`
lane on Intel Arc Pro B70.

## Model Identity

- Hugging Face repo: `Intel/Qwen3.6-27B-int4-AutoRound`
- Revision: `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`
- Base model: `Qwen/Qwen3.6-27B`
- License: Apache-2.0, following the base model license constraints
- Runtime target: vLLM/XPU first, one B70 per replica before any TP experiments
- Quantization: AutoRound INT4, `bits=4`, `group_size=128`, symmetric,
  `packing_format=auto_round:auto_gptq`
- Model card vLLM starting point:
  `--tensor-parallel-size 1 --max-model-len 2048 --reasoning-parser qwen3`
  with optional `qwen3_next_mtp` speculation at `num_speculative_tokens=2`

The model card reports ten safetensor shards plus
`model_extra_tensors.safetensors`; Hugging Face metadata reports about
`17.71 GiB` of tracked files.

## Current Status

Initial TP1 single-B70 vLLM/XPU bring-up passed on 2026-07-03. This is not a
speed claim yet.

Validated so far:

- pinned snapshot downloaded under `/mnt/fast-ai/llm-cache/hf`;
- TP1 vLLM server loaded on GPU0 at `max_model_len=2048`;
- vLLM auto-detected quantization as `inc` / AutoRound-compatible W4A16 path;
- model loaded in `17.84 GiB`;
- OpenAI smoke passed with thinking disabled;
- MTP2 is active and accepted `105/108` draft tokens across the smoke/manual
  probes, so the Intel checkpoint is not showing the public 0%-acceptance MTP
  packaging failure in this local runtime.

Next milestone: no-spec versus MTP2 fresh-response baselines, then XPU graph
and `num_speculative_tokens` sweeps under the fixed validity gate.

First diagnostic realistic-suite run (not a headline result):

- file:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/mtp2-xpugraph0-ctx2048-realistic-v1-reasoningdelta-20260703T013627Z.json`;
- config: TP1, MTP2, XPU graph off, `max_model_len=2048`,
  `max_tokens=128`, thinking disabled by request;
- median wall throughput: `36.327 tok/s`;
- median full-output after-TTFT throughput: `41.972 tok/s`;
- median TTFT: `484.821 ms`;
- validity: **diagnostic only** because `cached_tokens=null` and exact
  tokens-1-100 timing is not measurable from grouped SSE text chunks.

## Start Here

- [Reproduce](reproduce.md): download, launch, smoke, and benchmark entry
  points.
- [Validity gates](validity-gates.md): what counts as a baseline, record, or
  LocalMaxxing candidate.
- [Bugs and failed paths](bugs-failed-paths.md): loader/runtime failures and
  invalid speed lanes.
- Experiment lane:
  `../../experiments/qwen36-27b-autoround-int4-b70/README.md`.
- Research plan:
  `../../experiments/qwen36-27b-autoround-int4-b70/research-plan.md`.

## Initial Hypotheses

1. TP1 should fit on a single 32 GB B70 at short context because the checkpoint
   is INT4 AutoRound with FP16 exceptions, not full BF16.
2. The fastest research loop should use four independent TP1 replicas on the
   four B70s, mirroring the Gemma workflow, before considering TP2/TP4.
3. Built-in `qwen3_next_mtp` may provide an early speedup, but headline claims
   must still use fresh prompts with `cached_tokens=0` and target-verified
   accepted tokens.
4. Loader support is the first risk: local vLLM must correctly map
   `quant_method=auto-round` / `auto_round:auto_gptq` to an XPU-supported
   W4A16 path without silently dequantizing or CPU fallback.

## Do Not Claim Yet

- Do not submit LocalMaxxing results until the fixed realistic gate exists and
  passes.
- Do not average warmed repeated prompts into fresh-response throughput.
- Do not compare this INT4 quality lane directly against Gemma Q8 or Qwen35
  W8A8 without labeling the quantization and quality differences.
