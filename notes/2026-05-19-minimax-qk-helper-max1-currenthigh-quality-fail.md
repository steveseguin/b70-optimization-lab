# MiniMax Q/K Helper Max1 Current-High Quality Fail

Date: 2026-05-19

## Summary

This run tested the current MiniMax strict high-speed recipe with a narrower
Q/K RMS helper guard:

```bash
VLLM_MINIMAX_QK_RMS_XPU_HELPER=1
VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS=1
VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_SCALE=1
VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=1
VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1
VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4
```

The goal was to complete the small Q/K helper guard sweep around the current
promoted `max4` setting. This was rejected before benchmarking.

## Quality

The first strict canary failed:

- Gate: `raw145-n64-exact`
- Expected token hash: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Observed token hash: `21404821eb70a2ee3de9e82c039b5cbb5c9eef884c5019579f442c6a272a9c5a`
- Failure reason: `combined token hash mismatch`

The output was deterministic and non-degenerate, with no NUL/control-token
corruption:

- Distinct generated token count: `4`
- Printable non-space text chars: `256`
- Control non-space text chars: `0`
- NUL token count: `0`

This still violates the exact-output quality requirement, so no speed
benchmark was run.

## Decision

Reject. Do not benchmark. Do not submit to LocalMaxxing. Keep
`VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS=4` for the promoted recipe.

Guard sweep status for the current high:

- max1: quality fail at raw145 n64
- max2: quality-safe but slower (`88.541226` output tok/s)
- max4: current promoted high (`89.314195` output tok/s)
- max512: quality-safe but slower (`87.974187` output tok/s)

The useful lesson is that the helper guard changes more than just scheduling at
`max1`; it alters the captured execution enough to change exact output. That
makes max1 unusable under the current quality rule.

## Artifacts

- Strict summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-qk-helper-max1-currenthigh-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T203227Z-summary.json`
- Quality JSON: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-qk-helper-max1-currenthigh-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T203227Z-quality/raw145-n64-exact.json`
- Quality log: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-qk-helper-max1-currenthigh-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T203227Z-quality/raw145-n64-exact.log`
- Local data: `data/minimax-m27-qk-helper-max1-currenthigh-quality-fail-20260519.json`
