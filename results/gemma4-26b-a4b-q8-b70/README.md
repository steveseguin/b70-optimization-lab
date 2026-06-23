# Gemma 4 26B A4B Q8 on Intel B70

Status: **active optimization; current valid fresh-response best is llama.cpp
draft-MTP `n=7`, fast top-k, `91.62 tok/s` mean after TTFT / `91.25 tok/s`
first request / `71.29` wall tok/s, 384/384 chat canary, LocalMaxxing
`cmqqsecuk01azqo018ahv0i1s`**.

Draftless `ngram-mod` later reached `245-280 tok/s`, but only after repeated
benchmark requests made the same continuation predictable from generated
history. Those rows are useful warmed/history-accelerated artifacts, not valid
fresh-response headline throughput. The submitted ngram LocalMaxxing rows are
marked retraction-needed in this repo; API deletion was attempted on 2026-06-23
and returned 404 because LocalMaxxing exposes no benchmark delete endpoint.

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
- A separate latest-runtime worktree is available at
  `/home/steve/src/llama.cpp-latest-gemma`, built at `c926ad098` with AOT BMG
  output under
  `/home/steve/src/llama.cpp-latest-gemma/build-sycl-b70-aot-bmg-g31/bin/`.
  Use `--ctx-checkpoints 0` for record attempts on this runtime; the upstream
  default checkpointing hurts this benchmark's TTFT.
- There is enough disk for the Q8 GGUF; `/mnt/fast-ai` had about 353 GB free at
  lane start.
- The Q8 GGUF is downloaded and byte-verified at
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
  (`27,636,230,944` bytes). Metadata sidecar:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf.metadata.json`.
- Alternate Q8_0 GGUF is also downloaded for later comparison at
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-Q8_0.gguf`
  (`26,859,859,744` bytes). Do not promote it until it beats the Q8_K_XL
  frontier under the same canary and filled-long benchmark shape.
- The local editable `/home/steve/src/vllm` tree was used only for a controlled
  official-HF Gemma comparison after recording vLLM version/source identity.
  It is not competitive with llama.cpp Q8 today; see the vLLM row below.

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
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=6`, `n-min=2`, `p-min=0.15`, 384/384 canary; actual shape 588 input / 512 output tokens | **83.52 after TTFT** / 76.57 wall | [summary](../../data/gemma4-q8-gpu2-mtp-n6-aot-nmin2-pmin015-filled-long-deep-20260623T091227Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0912-filled-long-deeper-n-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=7`, `n-min=2`, `p-min=0.15`, 384/384 canary; actual shape 588 input / 512 output tokens | **87.88 after TTFT** / 80.25 wall | [summary](../../data/gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin015-filled-long-deep-20260623T091939Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0919-filled-long-n7-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=7`, `n-min=2`, `p-min=0.10`, 384/384 canary; actual shape 588 input / 512 output tokens | **88.35 after TTFT** / 80.55 wall | [summary](../../data/gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin010-filled-long-deep-20260623T092524Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0925-n7-pmin-and-psplit-sweeps.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=7`, `n-min=2`, `p-min=0.10`, `--no-spec-draft-backend-sampling`, 384/384 canary; actual shape 588 input / 512 output tokens | **90.24 after TTFT** / 82.24 wall | [summary](../../data/gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-filled-long-deep-20260623T093619Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0936-n7-backend-sampling-sweep.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=7`, `n-min=2`, `p-min=0.10`, `--no-spec-draft-backend-sampling`, `--spec-draft-threads 32`, 384/384 canary; actual shape 588 input / 512 output tokens | **90.42 after TTFT** / 82.34 wall | [summary](../../data/gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filled-long-deep-20260623T094131Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T0941-n7-nobs-followups.md) |
| 2026-06-23 | llama.cpp `dec5ca557` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU2 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous filled-long best: MTP `n=7`, `n-min=2`, `p-min=0.12`, `--no-spec-draft-backend-sampling`, `--spec-draft-threads 32`, `--spec-draft-threads-batch 32`, 384/384 canary; actual shape 588 input / 512 output tokens | **91.05 after TTFT** / 82.97 wall | [summary](../../data/gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T101814Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1018-dtb32-pmin-interaction.md) |
| 2026-06-23 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | previous fresh-response filled-long best: latest runtime, MTP `n=7`, `n-min=2`, `p-min=0.12`, `--no-spec-draft-backend-sampling`, `--spec-draft-threads 32`, `--spec-draft-threads-batch 32`, `--ctx-checkpoints 0`, 384/384 canary; actual shape 588 input / 512 output tokens | **91.16 after TTFT** / 71.06 wall | [summary](../../data/gemma4-q8-gpu0-mtp-n7-latest-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T113058Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1130-latest-runtime-c926ad098.md) |
| 2026-06-23 | llama.cpp `c926ad098` SYCL draft-MTP AOT BMG + fast top-k patch | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF + Gemma MTP draft GGUF, f16 KV | 8K | **current fresh-response filled-long best**: prior `n=7/n-min=2/p-min=0.12` recipe plus `LLAMA_MTP_DRAFT_FAST_TOPK=1`, `LLAMA_MTP_DRAFT_TOP_K=10`, backend sampling off, 384/384 canary; actual shape 588 input / 512 output tokens, first request `91.25 tok/s`, `cached_tokens=0` | **91.62 after TTFT** / 71.29 wall | [summary](../../data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1504-fast-topk.md) |
| 2026-06-23 | vLLM `0.20.2rc1.dev13+g9557d9108` XPU online quant | 1 replica on B70 GPU1/GPU2 | official HF Gemma 4 26B A4B, `int8_per_channel_weight_only` and FP8 diagnostics | 8K | compatibility comparison: INT8 graph passed 128/128 at `34.89 tok/s`; FP8 per-tensor passed 64/64 at `40.31 tok/s`; selector fix required `ONEAPI_DEVICE_SELECTOR=level_zero:*` + `ZE_AFFINITY_MASK` | **34.89 INT8** / **40.31 FP8 diagnostic** | [vLLM sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T2032-vllm-int8-fp8-smokes.md), [best INT8 summary](../../data/gemma4-vllm-int8pc-gpu1-piecewise-selectorfix-smoke-20260623T204041Z/summary.json), [best FP8 summary](../../data/gemma4-vllm-fp8tensor-gpu2-compile12-piecewise-smoke-20260623T205416Z/summary.json) |
| 2026-06-23 | llama.cpp `c926ad098` SYCL draftless ngram-mod AOT BMG | 1 replica on B70 GPU0 | UD-Q8_K_XL GGUF, f16 KV | 8K | warmed/history artifact: `ngram-mod match=20 min=32 max=64`, `--ctx-checkpoints 0`, 384/384 canary; repeated 588+512 output became predictable after prior identical generations. Submitted before fresh/warmed rule clarification; retraction-needed. | **255.04 warmed/history** / 137.00 wall | [summary](../../data/gemma4-q8-gpu0-ngram-mod-20-32-64-ctxcp0-filled-long-deep-20260623T1750/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1735-ngram-spec-sweep.md) |
| 2026-06-23 | llama.cpp `c926ad098` SYCL draftless ngram-mod AOT BMG | 1 replica on B70 GPU3 | UD-Q8_K_XL GGUF, f16 KV | 4K | warmed/history artifact: same `ngram-mod match=20 min=32 max=64`, `--ctx-checkpoints 0`, `UBATCH_SIZE=512`, `POLL=50`, 384/384 canary; not a fresh-response or 32K-context claim. Submitted before rule clarification; retraction-needed. | **280.04 warmed/history** / 206.50 wall | [summary](../../data/gemma4-q8-gpu3-ngram-mod-20-32-64-ctx4096ub512-ctxcp0-filled-long-deep-20260623T1815/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1735-ngram-spec-sweep.md) |
| 2026-06-23 | llama.cpp `c926ad098` SYCL draftless ngram-mod AOT BMG | 1 replica on B70 GPU1 | UD-Q8_K_XL GGUF, f16 KV | 4K | warmed/history artifact: same `ngram-mod match=20 min=32 max=64`, `--ctx-checkpoints 0`, `UBATCH_SIZE=512`, `POLL=100`, 384/384 canary; repeated 588+512 output became predictable from n-gram history. Submitted before rule clarification; retraction-needed. | **280.64 warmed/history** / 206.24 wall | [summary](../../data/gemma4-q8-gpu1-ngram-mod-20-32-64-ctx4096ub512-poll100-ctxcp0-filled-long-deep-20260623T1855/summary.json), [sweep note](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260623T1735-ngram-spec-sweep.md) |

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
tokens and 512 output tokens. On that shape, the best draft-MTP recipe reached
**91.62 tok/s** after TTFT with the source-level fast top-k draft bypass,
approved on LocalMaxxing as `cmqqsecuk01azqo018ahv0i1s`. Draftless
`ngram-mod` speculation later produced **280.64 tok/s** after TTFT with
`match=20, min=32, max=64`, `CTX_SIZE=4096`, `UBATCH_SIZE=512`, and
`POLL=100`, but that is warmed/history throughput: the repeated benchmark
output became predictable from prior generated continuation history. It is
valid Q8 verification of a warmed continuation, not fresh-response no-cache
decode. Do not use the submitted ngram LocalMaxxing rows as headline records;
the current fresh-response record remains the draft-MTP fast-top-k row above.
The after-TTFT decode metric is the promoted comparison metric. The wall/total
metric in repeated filled-long runs is warmed by the benchmark's repeated prompt
shape and can include substantial prompt-cache reuse after the first repeat; do
not compare it to a cold unique-prompt total-throughput benchmark without
labeling the difference.
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
