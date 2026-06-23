# Next Model Carryover

This Qwen3.6 35B Quark INT8 lane should now be treated as a reference, not the
main active optimization target. Move to another model unless doing a controlled
upstream/runtime bakeoff or a deliberate speculative-state engineering project.

## Prior Successful Lanes

- MiniMax M2.7: deployable 4x B70 baseline and production service material live
  under [`../../repro/minimax-m27-b70-110tps-ubuntu24-20260523/`](../../repro/minimax-m27-b70-110tps-ubuntu24-20260523/)
  and [`../../docs/current-reproducibility-map.md`](../../docs/current-reproducibility-map.md).
- Qwen 27B: prior optimized lane; useful references include
  [`q4_0-gguf-2026-05-03-four-b70-sycl.md`](../q4_0-gguf-2026-05-03-four-b70-sycl.md),
  [`q4_0-gguf-2026-05-04-sycl-single-kernel-allreduce.md`](../q4_0-gguf-2026-05-04-sycl-single-kernel-allreduce.md),
  and [`fp8-vllm-xpu-qwen36-2026-05-04.md`](../fp8-vllm-xpu-qwen36-2026-05-04.md).
- Gemma 4 12B AutoRound INT4: strong TP4/c8 production lane in
  [`../../experiments/gemma4-12b-int4-autoround-vllm/`](../../experiments/gemma4-12b-int4-autoround-vllm/).

## Gemma / Large-Model TP4 Lessons

The current repo has solid Gemma 4 12B TP4 material, not a validated Gemma 35B
TP4 recipe. For Gemma-family or other large TP4 work, carry over these limits:

- Production Gemma 4 12B c8 profile was validated at 32K with XPU graph and
  quality gates. See
  [`results-20260607-production-c8-xpugraph.json`](../../experiments/gemma4-12b-int4-autoround-vllm/results-20260607-production-c8-xpugraph.json).
- c8 short-prompt aggregate decode reached about `780 tok/s` class for Gemma 4
  12B, with LocalMaxxing-approved c8 records.
- c10 improved short-prompt aggregate throughput (`849.59 tok/s`) but did not
  improve near-32K throughput; it is research-only.
- c12 was rejected after `UR_RESULT_ERROR_OUT_OF_RESOURCES` and
  `UR_RESULT_ERROR_DEVICE_LOST`. KV estimates alone were not sufficient for
  production promotion.
- Near-32K unique prompts are a different regime than short-prompt decode. Do
  not promote based on short prompts alone.

Useful Gemma references:

- [`Gemma experiment README`](../../experiments/gemma4-12b-int4-autoround-vllm/README.md)
- [`Gemma production c8 XPU graph result`](../../experiments/gemma4-12b-int4-autoround-vllm/results-20260607-production-c8-xpugraph.json)
- [`Gemma c10/c12 32K boundary`](../../experiments/gemma4-12b-int4-autoround-vllm/results-20260607-c10-c12-32k-boundary.json)
- [`2026-06-06 Qwen35/Gemma candidates`](../../notes/2026-06-06-qwen35-gemma-autoround-candidates.md)

## Strategy For The Next Model

1. Establish a boring valid baseline before speculative decode.
2. Record the exact benchmark identity before every comparison.
3. Keep 2x and 4x results separate; TP2 can diagnose communication overhead but
   does not replace a 4x record.
4. Run JSON/color canaries early and often; run quality before promoting.
5. Preserve every meaningful failed patch and result with a short reason.
6. Submit LocalMaxxing only after the result is a real improvement for that GPU
   count and mode.

## What Not To Repeat

- Do not chase a fast number after canaries fail.
- Do not call a 16/16 or 32/32 smoke "solved" for a rare bug.
- Do not compare graph-none to PIECEWISE forced-comm graph.
- Do not treat synthetic accept or oracle paths as endpoint throughput.
- Do not keep iterating on Qwen3.6 35B Quark INT8 without a new upstream/runtime
  hypothesis; the local flag space is exhausted.
