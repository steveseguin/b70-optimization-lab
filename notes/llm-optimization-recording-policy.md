# LLM Optimization Recording Policy

Date: 2026-05-04

This file records the standing process for the B70 LLM optimization work.

## Local Notes

Record every meaningful experiment in `/home/steve/b70-llm-lab-notes.md` and keep the active plan in `/home/steve/q4_0-gguf-b70-optimization-plan.md`.

For each run, capture:

- model and exact local path;
- backend/runtime, source commit or package version when known;
- GPU selector/order, tensor/pipeline split, cache dtype, attention backend, and important environment flags;
- exact command or enough command shape to reproduce;
- prompt/output/context sizes, warmup/measured iterations, and batch/concurrency;
- log and JSON artifact paths;
- throughput, latency, reported memory/KV capacity, and failure mode if any;
- whether the result is recommended, diagnostic-only, failed, or quality-risky.

## GitHub

Push reproducibility artifacts to `steveseguin/llm-optimizations` when they are useful outside the current machine:

- patches needed to reproduce a working path or failure diagnosis;
- notes summarizing a result, failed path, or driver/backend behavior;
- JSON result summaries with log paths and exact metrics;
- install/build/run guidelines that would let the work be recreated from scratch.

Do not rely only on local `site-packages` edits. Any local runtime patch that affects results should also have a patch file or note in GitHub.

## LocalMaxxing

Submit to LocalMaxxing when a result is valid and useful to share:

- clear performance improvements;
- recommended operating points;
- diagnostic topology results that teach something reusable;
- meaningful negative results, if the submission notes make the limitation clear.

Do not submit:

- crashes or incomplete runs;
- cold smoke tests as if they were throughput results;
- quality-risky runs without explicitly marking the tradeoff;
- duplicate reruns unless they improve confidence or add a new dimension.

When submitting, include:

- exact model HF ID;
- hardware shape and GPU count;
- engine name/version and quantization;
- command snippet;
- tensor/pipeline parallelism, KV cache dtype, attention backend, context, concurrency, and relevant flags;
- notes explaining whether the run is recommended or diagnostic-only.

## Current Important Artifacts

- TP4 FP8 patched FA2 best result notes: `notes/2026-05-04-qwen36-fp8-b70-fa2.md` in GitHub.
- TP4 vs PP2xTP2 full-context notes: `notes/2026-05-04-qwen36-fp8-full-context-topologies.md` in GitHub.
- vLLM XPU FA2 singleton compressed-tensors scale patch: `patches/vllm-xpu-fa2-compressed-tensors-scalar-scales.patch` in GitHub.
- vLLM Qwen3.5 language-only vision skip patch: `patches/vllm-qwen35-language-model-only-skip-vision.patch` in GitHub.
- LocalMaxxing diagnostic PP2xTP2 result: `cmormmlz0000bky04wpu4oc01`.

## Qwen3.6 Decode Optimization Protocol

Standing goal: increase the single-request decode token rate of
`nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` without lowering quality.
Aggregate throughput still matters, but c1 decode latency is the lead metric.

For every task:

- update the active notes before or immediately after running experiments;
- record future ideas that look promising, even if they are not tested yet;
- record positive, neutral, and negative results with enough context to avoid
  retesting dead ends;
- preserve patches, scripts, command snippets, and compact JSON/Markdown
  artifacts for anything that changes a result or teaches a reusable lesson;
- keep raw logs out of commits unless they are necessary reproducibility
  artifacts, and summarize large logs into compact files;
- do not promote speed unless quality and reliability gates pass.

Promotion gates for a candidate improvement:

- exact same model and quantization unless the experiment is explicitly marked
  out-of-scope;
- canary/token-ID quality checks before and after endpoint restart;
- adjacent accepted-control A/B run with warmups discarded;
- repeated steady-state measurements, preferably at least four measured runs;
- clear runtime provenance: vLLM source/patch, oneAPI/oneCCL/PyTorch stack,
  driver/kernel, rank map, context length, cache root, and launch flags;
- single-request and aggregate behavior reported separately;
- cold-start, readiness-warmed, and persistent-engine numbers kept separate.

Current incremental stack priorities:

1. Decisive all-rank layer-family and collective timing.
2. Collective-only TP4/TP2/TP3 replay if synchronization dominates.
3. Persistent W8A8 MoE layerlet if MoE dispatch/GEMM dominates.
4. Oracle `k=1` parity repair before any speculative speed claim.
5. TP4 bypass or hybrid layouts only after timing says all-rank sync is the wall.
