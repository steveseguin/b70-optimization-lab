# MiniMax Q/K Post-Allreduce Apply Custom-Op Patch

Date: 2026-05-20

## Purpose

Test whether a narrower custom-op boundary around the post-allreduce Q/K RMS apply path could remove framework overhead without changing math.

The candidate intentionally kept the promoted operation order:

1. compute Q/K variance with `minimax_qk_rms_xpu.var_alloc`
2. perform the existing tiny FP32 `vllm.all_reduce_inplace`
3. scale `qk_var` in-place by `1 / tp_world`
4. call the existing XPU `apply_alloc` / `apply_f32_weight_alloc` helper

## Files Changed

- `/home/steve/src/vllm/vllm/model_executor/models/minimax_m2.py`
- `/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/vllm/model_executor/models/minimax_m2.py`
- `/home/steve/llm-optimizations-publish/scripts/run-minimax-strict-quality-gated-candidate.sh`

## New Flag

`VLLM_MINIMAX_QK_RMS_POST_AR_APPLY_CUSTOM_OP=1`

Default is off.

## Outcome

Full strict quality passed, but throughput was effectively tied:

- Candidate: `89.328078` output tok/s / `119.104104` total tok/s
- Promoted baseline: `89.314195` output tok/s / `119.085594` total tok/s
- Delta: `+0.0155%`

The candidate repeatedly logged `ocloc` 245 / IGC floating point exceptions during graph capture. Do not promote and do not set the flag in the default recipe.
