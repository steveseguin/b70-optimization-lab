# Gemma 4 26B A4B Q8 on Intel B70

Status: **active optimization; current valid best is llama.cpp draft-MTP
`n=6, n-min=2, p-min=0.15` on the filled-long shape**.

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
- The Q8 GGUF is downloaded and byte-verified at
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
  (`27,636,230,944` bytes). Metadata sidecar:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf.metadata.json`.
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
| 2026-06-23 | llama.cpp `dec5ca557` SYCL | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF, f16 KV | 8K | **valid baseline**: chat canary 128/128; reasoning off | **26.10 after TTFT** / 24.24 wall | [summary](../../data/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T052850Z-valid-baseline-reasoning-off.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF, f16 KV | 8K | **current natural-stop best**: `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `--parallel 1 --cache-ram 0`, chat canary 384/384; reasoning off | **42.15 after TTFT** / 36.41 wall | [summary](../../data/gemma4-q8-gpu2-syclopt0-faoff-parallel1-cache0-deep-20260623T0915/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0900-parallel-cache-followups.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF, f16 KV | 8K | sustained-decode best before MTP: same config, `BENCH_PROMPT_MODE=long`, 384/384 canary; actual shape is about 75 input / 512 output tokens | **42.72 after TTFT** / 41.35 wall | [summary](../../data/gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0930-long-output-benchmark.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | MTP `n=4`: `--spec-type draft-mtp --spec-draft-n-max 4`, 384/384 canary; actual shape 75 input / 512 output tokens | **44.50 after TTFT** / 43.03 wall | [summary](../../data/gemma4-q8-gpu1-mtp-n4-long-deep-20260623T1140/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1125-mtp-draft-smoke-and-deep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | MTP `n=3`: `--spec-type draft-mtp --spec-draft-n-max 3`, 384/384 canary; actual shape 75 input / 512 output tokens | **46.36 after TTFT** / 44.75 wall | [summary](../../data/gemma4-q8-gpu1-mtp-n3-long-deep-20260623T0328/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0328-mtp-near-optimum-deep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | repeated MTP `n=3`, 384/384 canary; actual shape 75 input / 512 output tokens | **47.63 after TTFT** / 45.93 wall | [summary](../../data/gemma4-q8-gpu0-mtp-n3-repeat-long-deep-20260623T0337/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0337-mtp-n3-followups.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | AOT `bmg-g31`, MTP `n=3`, 384/384 canary; actual shape 75 input / 512 output tokens | **47.92 after TTFT** / 46.18 wall | [summary](../../data/gemma4-q8-gpu3-mtp-n3-aot-bmg-long-deep-20260623T0345/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0345-mtp-n3-aot-and-runtime.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | repeated AOT `bmg-g31`, MTP `n=3`, 384/384 canary; actual shape 75 input / 512 output tokens | **48.35 after TTFT** / 46.60 wall | [summary](../../data/gemma4-q8-gpu0-mtp-n3-aot-repeat-long-deep-20260623T0353/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0353-mtp-aot-n-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | filled-long prompt shape, MTP `n=3`, 384/384 canary; actual shape 588 input / 512 output tokens | **68.19 after TTFT** / 63.43 wall | [summary](../../data/gemma4-q8-gpu3-mtp-n3-aot-filled-long-deep-20260623T085322Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0853-filled-long-mtp-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | filled-long prompt shape, MTP `n=3` + `--spec-draft-p-split 0.20`, 384/384 canary; actual shape 588 input / 512 output tokens | **68.51 after TTFT** / 63.67 wall | [summary](../../data/gemma4-q8-gpu2-mtp-n3-aot-psplit020-filled-long-deep-20260623T085844Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0853-filled-long-mtp-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | filled-long prompt shape, MTP `n=4`, 384/384 canary; actual shape 588 input / 512 output tokens | **74.39 after TTFT** / 68.80 wall | [summary](../../data/gemma4-q8-gpu3-mtp-n4-aot-filled-long-deep-20260623T085822Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0853-filled-long-mtp-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=4` + `--spec-draft-p-split 0.20`, 384/384 canary; actual shape 588 input / 512 output tokens | **74.50 after TTFT** / 68.90 wall | [summary](../../data/gemma4-q8-gpu1-mtp-n4-aot-psplit020-filled-long-deep-20260623T090712Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0907-filled-long-n4-followups.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | filled-long prompt shape, MTP `n=5`, 384/384 canary; actual shape 588 input / 512 output tokens | **78.64 after TTFT** / 72.25 wall | [summary](../../data/gemma4-q8-gpu1-mtp-n5-aot-filled-long-deep-20260623T091227Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0912-filled-long-deeper-n-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | **current sustained-decode best**: filled-long prompt shape, MTP `n=6`, `n-min=2`, `p-min=0.15`, 384/384 canary; actual shape 588 input / 512 output tokens | **83.52 after TTFT** / 76.57 wall | [summary](../../data/gemma4-q8-gpu2-mtp-n6-aot-nmin2-pmin015-filled-long-deep-20260623T091227Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0912-filled-long-deeper-n-sweep.md) |

The first valid result is intentionally labeled as a baseline, not an optimized
result. It proves that the Q8 GGUF fits and serves correctly at 8K on one B70,
but the decode rate is far below the public LocalMaxxing Gemma 4 family context
and should be treated as the control for four-at-a-time optimization sweeps.

`GGML_SYCL_DISABLE_OPT=0` is the largest speed lever so far despite an upstream
B70/Gemma corruption report for that flag. The promoted
`FLASH_ATTN=off --parallel 1 --cache-ram 0` variant passed a promotion-depth
deterministic chat gate (`96` repeats x `4` cases = `384/384`) before being
promoted. Treat any further optimized-SYCL variants as risky until they pass the
same or stronger gate.

The 42.72 tok/s no-spec sustained-decode row uses the same valid runtime
identity as the 42.15 natural-stop row, but a different benchmark prompt shape.
The model is forced to generate the full 512-token budget, so wall throughput
rises because TTFT is amortized over more output tokens.

The `long` prompt mode is a short 75-token prompt that forces 512 output tokens.
The newer `filled-long` mode is the current preferred record-chasing shape for
this lane because it produces a near-p512/o512 request in practice: 588 prompt
tokens and 512 output tokens. On that shape the official Gemma MTP draft GGUF is
much more valuable, and `--spec-draft-n-max 6 --spec-draft-n-min 2
--spec-draft-p-min 0.15` is the current valid best at 83.52 tok/s after TTFT.
Keep natural-stop, short-prompt
sustained-decode, and filled-long sustained-decode records separate when
comparing future runs, and keep MTP runs separate from no-spec runs unless
prompt/output shape and canary depth match.

## Linked Files

- [Reproduction commands](reproduce.md)
- [Validity gates](validity-gates.md)
- [Runtime plan](runtime-plan.md)
- [Research plan and experiment queue](research-plan.md)
- [Model and runtime options](model-options.md)
- [LocalMaxxing targets and submission packet](localmaxxing-and-targets.md)
- [Bugs and failed paths](bugs-failed-paths.md)
- [Active experiment folder](../../experiments/gemma4-26b-a4b-q8-b70/README.md)
