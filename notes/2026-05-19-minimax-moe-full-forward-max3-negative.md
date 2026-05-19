# MiniMax MoE Full Forward Max3 Negative

Date: 2026-05-19

## Summary

This run kept the current strict MiniMax high-speed recipe but narrowed the
guarded MiniMax MoE full-forward custom-op boundary from decode-sized tensors
up to 4 tokens down to 3 tokens:

```bash
VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1
VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=3
```

The goal was to complete the boundary sweep around the current max4 recipe
after max1, max2, and max512 all failed to improve throughput.

## Quality

Strict quality passed before benchmarking:

- `raw145-n64-exact`
- `raw145-n256-exact`
- `semantic-suite-n64-r2`
- `arithmetic-repeat-n64-r16`
- `extended-sixpack-n64-r2`

The exact raw145 token hashes matched the promoted references:

- n64: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- n256: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`

Additional repeatability hashes also matched the current promoted high:

- semantic suite n64/r2: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic repeat n64/r16: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack n64/r2: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

As with max2, one quality subprocess printed `Bad address (src/pipe.cpp:367)`
during shutdown, but the strict runner continued, the quality JSONs were valid,
and all four benchmark repeats completed.

No quality-reducing changes were used: no speculative decoding, no expert
dropping, no router approximation, no quantization change, and no power-limit
change.

## Performance

Shape: p512/n1536, ctx2048, batch 1, TP4, 4x B70.

- Output tok/s samples: `88.710302`, `88.946034`, `89.043467`, `88.844831`
- Total tok/s samples: `118.280403`, `118.594712`, `118.724623`, `118.459775`
- Mean: `88.886159` output tok/s, `118.514878` total tok/s

The current promoted strict high remains:

- `89.314195` output tok/s
- `119.085594` total tok/s
- LocalMaxxing: `cmpct6t4m007fnw01yjdtlcs4`

This candidate is `-0.428037` output tok/s (`-0.479%`) below the promoted
mean.

## Decision

Do not promote. Do not submit to LocalMaxxing. Keep
`VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4` for the current speed
recipe.

This completes the local guard-size sweep:

- max1: `89.031893` output tok/s
- max2: `88.854010` output tok/s
- max3: `88.886159` output tok/s
- max4: `89.314195` output tok/s, current high
- max512: `85.209082` output tok/s

The useful lesson is that the max4 decode-sized custom-op boundary is the
repeatable local optimum among the tested guard sizes.

## Artifacts

- Strict summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-fullforward-max3-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T185227Z-summary.json`
- Quality directory: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-fullforward-max3-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T185227Z-quality`
- Local data: `data/minimax-m27-moe-full-forward-max3-negative-20260519.json`
