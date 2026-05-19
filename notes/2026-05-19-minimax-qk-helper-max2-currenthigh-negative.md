# MiniMax Q/K Helper Max2 Current-High Negative

Date: 2026-05-19

## Summary

This run retested the MiniMax Q/K RMS XPU helper on top of the current strict
high-speed recipe, but lowered the helper guard from the promoted decode guard
of four tokens to two tokens:

```bash
VLLM_MINIMAX_QK_RMS_XPU_HELPER=1
VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS=2
VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_SCALE=1
VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=1
VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1
VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4
```

The goal was to check whether a narrower Q/K helper graph guard improved
single-stream decode scheduling while preserving exact quality.

## Quality

Strict quality passed before benchmarking:

- `raw145-n64-exact`
- `raw145-n256-exact`
- `semantic-suite-n64-r2`
- `arithmetic-repeat-n64-r16`
- `extended-sixpack-n64-r2`

The exact quality hashes matched the promoted references:

- raw145 n64: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite n64/r2: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic repeat n64/r16: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack n64/r2: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

No quality-reducing changes were used: no speculative decoding, no expert
dropping, no router approximation, no quantization change, and no power-limit
change.

## Performance

Shape: p512/n1536, ctx2048, batch 1, TP4, 4x B70.

- Output tok/s samples: `88.586276`, `87.924950`, `88.831272`, `88.822405`
- Total tok/s samples: `118.115034`, `117.233267`, `118.441696`, `118.429874`
- Mean: `88.541226` output tok/s, `118.054968` total tok/s

The current promoted strict high remains:

- `89.314195` output tok/s
- `119.085594` total tok/s
- LocalMaxxing: `cmpct6t4m007fnw01yjdtlcs4`

This candidate is `-0.772970` output tok/s (`-0.865%`) below the promoted
mean.

## Decision

Do not promote. Do not submit to LocalMaxxing. Keep
`VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS=4` for the promoted recipe.

The useful lesson is that the Q/K helper remains quality-safe at the narrower
two-token guard, but the current B70 decode path prefers the four-token helper
guard already used by the high. This supports treating graph guard shape as a
real performance variable, not just a correctness guard.

## Artifacts

- Strict summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-qk-helper-max2-currenthigh-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T195944Z-summary.json`
- Quality directory: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-qk-helper-max2-currenthigh-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T195944Z-quality`
- Local data: `data/minimax-m27-qk-helper-max2-currenthigh-negative-20260519.json`
