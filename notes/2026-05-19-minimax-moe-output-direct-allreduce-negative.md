# MiniMax M2.7 MoE Output Direct-Allreduce Negative

Date: 2026-05-19

## Summary

Tested `VLLM_MINIMAX_MOE_OUTPUT_DIRECT_ALLREDUCE=1` on top of the current strict high. The candidate kept the MiniMax MoE output allreduce inside the MoE custom-op boundary, but bypassed the clone-safe `tensor_model_parallel_all_reduce` wrapper for the MoE output tensor and called the TP group's direct out-of-place allreduce path.

This targeted the site-labeled timing bucket where MoE-output FP16 hidden-state allreduce still consumed visible synchronized time even after the full-forward MoE custom-op promotion.

## Result

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Runtime: vLLM `0.20.1-local`, XPU TP4
- Shape: p512/n1536, ctx2048, MBT512, block256, batch 1
- Candidate: `VLLM_MINIMAX_MOE_OUTPUT_DIRECT_ALLREDUCE=1`
- Mean output tok/s: `88.843823`
- Mean total tok/s: `118.458431`
- Output repeats: `87.591957`, `89.113233`, `89.706051`, `88.964052`
- Current promoted mean output tok/s: `89.314195`
- Delta: `-0.470372` output tok/s, about `-0.53%`

## Quality

The candidate passed the negative-candidate strict gate before benchmarking:

- raw145 n64 exact hash: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact hash: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite hash: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic repeat n64/r8 hash: `261779104d5abf1642713bfc560ca8d2d6c0f16edbcc929c8b0819b5a760dd7c`
- extended sixpack hash: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

No quality or benchmark logs contained `Traceback`, `Exception`, `Bad address`, `Broken pipe`, `failed`, or startup guard hits.

## Decision

Reject and do not submit to LocalMaxxing. The candidate was quality-clean for this gate, but slower than the current promoted high. The active source and installed venv were reverted after recording.

Lesson: the remaining MoE-output allreduce cost is not improved by replacing the wrapper with the TP group's direct out-of-place allreduce from Python. Future MoE-output work should move lower, either into a fused epilogue/allreduce path or into graph scheduling that reduces a real device/collective dependency rather than only changing the Python collective call.

## Artifacts

- Summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-moe-output-direct-allreduce-currenthigh-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T230120Z-summary.json`
- Patch: `patches/minimax-moe-output-direct-allreduce-negative-20260519.patch`
- Data: `data/minimax-m27-moe-output-direct-allreduce-negative-20260519.json`
