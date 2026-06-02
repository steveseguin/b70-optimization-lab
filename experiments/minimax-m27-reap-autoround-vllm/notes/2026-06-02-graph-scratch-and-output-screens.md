# 2026-06-02 Graph Scratch and Output Screens

Goal: continue REAP MiniMax-M2.7 AutoRound INT4 decode optimization after
restoring the quality-clean logits-WS lane. These were low-risk screens around
wrapper overhead, Q/K clean-weight graph state, output handling, and MiniMax WS
scratch reuse.

## Accepted Baseline For Comparison

Restored conservative lane:

- model: `/mnt/fast-ai/llm-models/minimax-m2.7-reap-autoround-w4a16`
- cache: `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-restored-u4runtime-20260602T1330`
- key env: logits-WS on, full-forward custom op off, attention-delay on,
  Q/K helper off, Q/K restore off, pidfd CCL
- restored quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-restored-u4runtime-logitsws-qk0-20260602T1330.json`
- restored single-run decode:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-restored-u4runtime/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T133537Z.json`,
  `84.229293276551` output tok/s
- restored repeat:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-restored-u4runtime-repeat/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T134137Z.json`,
  `84.60980634691803` output tok/s
- restored persistent warm mean:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/warm/warm-restored-u4runtime-logitsws-qk0-p512n1536-20260602T1345.json`,
  `85.35835544294164` output tok/s

## Rejected: Guarded Contiguous Wrapper

Patch archived:

`patches/llm-scaler-minimax-ws-guarded-contiguous-rejected-20260602.patch`

The active MiniMax WS wrapper still calls `.contiguous()` on tensors that vLLM
has already prepared as contiguous. I tested replacing those calls with a helper
that only calls `.contiguous()` when needed.

Quality failed:

- file:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-guardcontig-logitsws-qk0-20260602T135124Z.json`
- failure: mostly token id `0` / control output
- combined quality: `384` generated tokens, only `2` distinct token ids,
  `381` NUL tokens

Decision: reject and revert. Even this small Python wrapper guard perturbs the
compiled async graph into the known all-NUL failure mode.

## Rejected: Pre-Capture Clean-XPU Q/K Restore

Tested current logits-WS lane with:

- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1`
- `VLLM_MINIMAX_QK_NORM_PRECAPTURE_SANITIZE=1`
- `VLLM_MINIMAX_QK_NORM_PRECAPTURE_USE_PARAM=0`
- `VLLM_MINIMAX_QK_NORM_COMPILE_USE_PARAM=0`
- Q/K helper off

The sanitizer ran on all Q/K norms and found sane weights, but quality still
failed with the same all-NUL signature:

- file:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-restore1-precapture-cleanxpu-qk0-20260602T135837Z.json`
- cache:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-logitsws-restore1-precapture-cleanxpu-qk0-20260602T135837Z`
- failure: `384` generated tokens, only `2` distinct token ids,
  `381` NUL tokens

Decision: reject. Recreating the old clean-side-tensor graph shape is still not
quality-safe, even when the clean XPU clones are refreshed before capture.

## Output-Side Screen

Tested on restored cache:

- `VLLM_XPU_REUSE_ASYNC_OUTPUT_COPY_BUFFER=1`
- `VLLM_XPU_FAST_ASYNC_OUTPUT_LIST=1`
- `VLLM_XPU_FAST_ASYNC_UPDATE_OUTPUT_IDS=1`

Benchmark:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-outputfast/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T140346Z.json`
- total: `112.92520182036314` tok/s
- output-equivalent: about `84.69` tok/s

The p512/n256 timing probe also showed output conversion is not material:

- log:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/profile-restored-logitsws/vllm-minimax-m27-autoround-tp4-p512n256-20260602T140612Z.log`
- timing JSON:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/profile-restored-logitsws/vllm-minimax-m27-autoround-tp4-p512n256-20260602T140612Z.timing.json`
- `gpu_model_runner.async_output_tolist`: `0.003481 ms` average

Decision: reject as an optimization target. Output handling is not the current
decode bottleneck.

## Rejected: MiniMax WS Top-K Scratch Reuse

Tested:

- `VLLM_XPU_MINIMAX_WS_REUSE_TOPK_BUFFERS=1`

Quality passed on the restored cache:

- file:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-reusetopk-qk0-20260602T140853Z.json`
- result: passed, no NUL/control output

Single vLLM bench was neutral:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-reusetopk/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T141023Z.json`
- total: `112.99863857988167` tok/s
- output-equivalent: about `84.75` tok/s

Persistent warm-repeat regressed badly:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/warm/warm-reusetopk-logitsws-qk0-p512n1536-20260602T141238Z.json`
- mean output: `51.59589170272522` tok/s
- mean total: `68.79452227030029` tok/s

Decision: reject. The scratch aliasing path can pass a short quality smoke, but
it is not performance-safe across repeated requests in one engine.

## Current State

No new LocalMaxxing submission. The best current quality-clean REAP result from
live source remains the restored logits-WS lane:

- persistent warm mean: `85.35835544294164` output tok/s
- best historical REAP submission remains the archived `89.49922316987691`
  output tok/s result, but that exact fast graph shape has not been reproduced
  quality-clean from the current source/cache state.

Next useful work should target real GPU-side work:

- MiniMax WS kernel fusion or top-k plus up-kernel integration, not scratch
  aliasing.
- Q/K norm graph repair that avoids clean side tensors but reduces the current
  live-parameter graph cost.
- A graph/cache diff workflow that preserves whole cache roots before source
  instrumentation and compares code hash, AOT key, and captured graph structure.
