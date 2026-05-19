# MiniMax QKV Narrow Split Negative

Date: 2026-05-19

## Summary

This run tested a math-preserving attention-side micro-optimization on top of
the current MiniMax strict high-speed recipe:

```bash
VLLM_MINIMAX_QKV_NARROW_SPLIT=1
```

The patch replaces the Python `qkv.split(...)[2]` value view, and the fallback
`q, k, v = qkv.split(...)` path, with explicit `Tensor.narrow()` views. The
intent was to reduce graph/view overhead around the MiniMax Q/K RMS helper
without changing logits, routing, quantization, attention math, or sampling.

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

The arithmetic-repeat and extended-sixpack subprocesses printed
`Bad address (src/pipe.cpp:367)` during shutdown cleanup, but their quality
JSONs were valid, the strict runner continued, and all four benchmark repeats
completed. This matches the benign IPC cleanup warning already seen in other
quality-passed candidates.

No quality-reducing changes were used: no speculative decoding, no expert
dropping, no router approximation, no quantization change, and no power-limit
change.

## Performance

Shape: p512/n1536, ctx2048, batch 1, TP4, 4x B70.

- Output tok/s samples: `88.642812`, `88.632026`, `88.922560`, `89.013103`
- Total tok/s samples: `118.190416`, `118.176034`, `118.563413`, `118.684138`
- Mean: `88.802625` output tok/s, `118.403500` total tok/s

The current promoted strict high remains:

- `89.314195` output tok/s
- `119.085594` total tok/s
- LocalMaxxing: `cmpct6t4m007fnw01yjdtlcs4`

This candidate is `-0.511570` output tok/s (`-0.573%`) below the promoted
mean.

## Decision

Do not promote. Do not submit to LocalMaxxing. Keep
`VLLM_MINIMAX_QKV_NARROW_SPLIT` unset for the promoted recipe.

The useful lesson is that replacing split views with explicit narrow views is
quality-safe but does not reduce the current decode bottleneck under XPU graph
replay. The bottleneck remains more likely in compiled attention/MoE kernels,
collective boundaries, or graph scheduling than in this Python view selection.

## Artifacts

- Strict summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-qkv-narrow-split-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T192510Z-summary.json`
- Quality directory: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-qkv-narrow-split-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T192510Z-quality`
- Local data: `data/minimax-m27-qkv-narrow-split-negative-20260519.json`
- Patch notes: `patches/minimax-qkv-narrow-split-negative-20260519.patch`
