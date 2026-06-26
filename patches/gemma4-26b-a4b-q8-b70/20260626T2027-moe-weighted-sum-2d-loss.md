# Gemma 4 26B Q8: MoE Weighted-Sum 2D Launch Loss

Date: 2026-06-26

Status: rejected / quality-safe non-win.

## Intent

Test a default-off SYCL backend variant for `GGML_OP_MOE_WEIGHTED_SUM`:

- gate: `LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D=1`;
- current path: flattened 1D launch over `n_tokens * n_embd`, computing
  `row = idx % n_embd` and `token = idx / n_embd` per output element;
- experiment path: 2D launch over `token x row`, preserving all tensor strides
  and the exact weighted sum.

The hypothesis was that removing per-output div/mod overhead might help the
accepted Gemma MoE path without touching MTP, selected-softmax, route-cache, or
GEGLU/down fused paths.

## Source Delta Summary

In `/home/steve/src/llama.cpp-gemma-record-stack/ggml/src/ggml-sycl/ggml-sycl.cpp`:

- added `ggml_sycl_gemma4_moe_weighted_sum_2d_enabled()`;
- added `moe_weighted_sum_f32_sycl_2d(...)`;
- routed `ggml_sycl_moe_weighted_sum(...)` to the 2D variant only when
  `LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D=1`.

In the reproducibility repo:

- `scripts/run-gemma4-26b-first-baseline.sh` records
  `llama_gemma4_moe_weighted_sum_2d` in `summary.json`;
- `scripts/run-gemma4-26b-llamacpp-replica.sh` prints
  `LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D` in launch logs.

## Results

All runs used the current Q8 record family:

- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.136`;
- selected-softmax + weighted-sum + route-cache current stack;
- `BENCH_PROMPT_MODE=filled-long`, actual `588` prompt / `512` output tokens;
- fresh headline rule: row0 only, cached tokens must be zero.

Screen and full summaries:

- `data/gemma4-q8-gpu2-moe-weightedsum-2d-screen-20260626T202719Z/summary.json`
  - `128/128` canary, cached `[0, 0]`
  - fresh row0 `103.5435126657234`
  - support mean `102.539530590951`
- `data/gemma4-q8-gpu0-moe-weightedsum-2d-screen-20260626T202959Z/summary.json`
  - `128/128` canary, cached `[0, 0]`
  - fresh row0 `101.35034097096046`
  - support mean `102.34984602482261`
- `data/gemma4-q8-gpu1-moe-weightedsum-2d-screen-20260626T202959Z/summary.json`
  - `128/128` canary, cached `[0, 0]`
  - fresh row0 `101.48255322931645`
  - support mean `102.3812573687189`
- `data/gemma4-q8-gpu3-moe-weightedsum-2d-screen-20260626T202959Z/summary.json`
  - `128/128` canary, cached `[0, 0]`
  - fresh row0 `102.99795406628424`
  - support mean `102.08773488585275`
- `data/gemma4-q8-gpu2-moe-weightedsum-2d-full-20260626T202959Z/summary.json`
  - `1536/1536` canary, cached `[0, 0, 0, 0, 0, 0, 0, 0]`
  - fresh row0 `103.5104909373625`
  - support mean `103.26493464181871`
  - support median `103.42693492994971`

Current valid record remained:

- fresh row0 `103.51547512013657`;
- support mean `103.19340167720759`;
- LocalMaxxing `cmqvbq8tf02m1qr010dom0vu1`.

## Decision

Reject as a headline result and do not submit to LocalMaxxing.

The first GPU2 screen barely exceeded the record, but the full validation did
not. Other screens were lower. The path is quality-safe and default-off, so it
can remain as a reference experiment, but it should not be enabled in promoted
Gemma Q8 recipes unless a later source change makes weighted-sum launch shape a
larger bottleneck.

