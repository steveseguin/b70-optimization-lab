# MiniMax M2.7 Promoted Path Quality Sanity After Exact-Shape Gate

Date: 2026-05-21

## Summary

After adding the default-off `VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_SHAPES` diagnostic gate, I reran the promoted MiniMax M2.7 strict quality suite with the exact-shape gate unset. The promoted configuration still passes all quality checks.

This was a quality-only sanity run. No performance benchmark was recorded and no LocalMaxxing submission is warranted from this run.

## Result

- Status: `quality_passed`
- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Runtime: vLLM `0.20.1`, XPU, TP4, PIECEWISE graph capture
- Exact-shape gate: unset / default off
- Active allreduce controls:
  - `VLLM_XPU_CUSTOM_ALLREDUCE_TINY_FP32_INPLACE_MAX_NUMEL=2`
  - `VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_MAX_NUMEL=0`
  - `VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_SHAPES=""`

## Passed Checks

| Check | Combined token SHA256 |
| --- | --- |
| `raw145-n64-exact` | `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd` |
| `raw145-n256-exact` | `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537` |
| `semantic-suite-n64-r2` | `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805` |
| `arithmetic-repeat-n64-r16` | `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994` |
| `extended-sixpack-n64-r2` | `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7` |

All checks reported deterministic outputs and no quality failure reasons.

## Artifacts

- Summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-promoted-defaultoff-after-shapegate-quality-20260521-strict-tp4-ctx2048-mbt512-bs256-20260521T090459Z-summary.json`
- Per-check artifacts: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-promoted-defaultoff-after-shapegate-quality-20260521-strict-tp4-ctx2048-mbt512-bs256-20260521T090459Z-quality/`

## Compiler Note

The first raw check logged an Intel compiler fallback:

- Triton kernel: `triton_red_fused__to_copy_mm_t_9`
- Tool: `ocloc`
- Device: `bmg`
- Error: `IGC: Internal Compiler Error: Floating point exception`
- Exit status: `245`

The run recovered and all quality hashes still matched. This remains a future optimization/debugging target because avoiding failed compile attempts may improve cold-start stability and reduce graph-capture overhead, but it is not evidence of output corruption in the promoted path.
