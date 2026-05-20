# MiniMax Q/K Post-Allreduce Apply Custom-Op Neutral Screen

Date: 2026-05-20

## Summary

This candidate wrapped the decode-sized MiniMax Q/K RMS post-allreduce scale plus XPU apply helper in a default-off vLLM custom-op boundary:

- `VLLM_MINIMAX_QK_RMS_POST_AR_APPLY_CUSTOM_OP=1`
- current promoted stack otherwise unchanged
- p512/n1536, ctx2048, TP4, block size 256, max batched tokens 512

The intent was to preserve the current proven math ordering:

1. `minimax_qk_rms_xpu.var_alloc(qkv, q_size, kv_size)`
2. `vllm.all_reduce_inplace(qk_var)`
3. in-place `qk_var *= 1 / tp_world`
4. existing `minimax_qk_rms_xpu.apply_*_alloc(...)`

Quality passed completely, but speed was effectively tied with the promoted baseline and the candidate introduced recurring Intel `ocloc`/IGC internal compiler errors during graph capture. This is not a promotion and was not submitted to LocalMaxxing.

## Result

Baseline promoted mean:

- Output tok/s: `89.31419538094708`
- Total tok/s: `119.08559384126276`

Candidate:

- Output tok/s repeats: `[89.70298860597782, 88.73127218214572, 89.71503177345464, 89.16301890817525]`
- Output tok/s mean: `89.32807786743837`
- Total tok/s repeats: `[119.60398480797043, 118.30836290952762, 119.62004236460619, 118.88402521090033]`
- Total tok/s mean: `119.10410382325115`

Delta:

- Output: `+0.01388248649128343` tok/s, `+0.015543426699493601%`
- Total: `+0.01850998198838738` tok/s, `+0.015543426699515805%`

This is inside normal run noise. Treat it as neutral, not faster.

## Quality

Strict gates passed before benchmarking:

- raw145 n64 exact: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic repeat n64/r8: `261779104d5abf1642713bfc560ca8d2d6c0f16edbcc929c8b0819b5a760dd7c`
- extended sixpack n64/r2: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

Summary artifact:

- `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-qk-post-ar-apply-customop-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T031823Z-summary.json`

## Reliability Signal

The run repeatedly logged:

- `Triton compilation failed: triton_red_fused__to_copy_mm_t_9`
- `ocloc failed with error code 245`
- `IGC: Internal Compiler Error: Floating point exception`

The previous index-candidate throughput logs checked did not show these hits, so this is likely tied to the new custom-op boundary or graph shape. Since the speed delta is negligible and the compiler signal is weaker, leave this flag unset.

## Decision

Do not promote.

Do not submit to LocalMaxxing.

Keep the patch documented as a negative/neutral source-level lesson: Python custom-op boundaries around the already-optimized Q/K helper are not enough; the next useful Q/K work needs to be lower-level XPU/SYCL or compiler scheduling, not another wrapper around the same kernels.
