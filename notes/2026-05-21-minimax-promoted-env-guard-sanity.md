# MiniMax M2.7 Promoted Env Guard Sanity - 2026-05-21

## Goal

After the upstream-style XPU custom-op collective screen produced degenerate
NUL/control output, update the reproducibility environment to explicitly keep
that path disabled and verify the promoted MiniMax stack still matches the
known-good raw145 token hash.

The reproduction env now includes:

```bash
export VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=0
```

This is a quality/reproducibility guard, not a speed optimization.

## Quality Result

The promoted path passed the raw145 n64 exact-output canary after adding the
guard:

- Passed: `true`
- Expected-token hash match: `true`
- Combined token SHA256:
  `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Failure reasons: none
- NUL token count: `0`
- Control output: `false`

This confirms the active promoted path still preserves output quality after the
custom-op collective rejection.

## Decision

Keep `VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=0` in the reproducibility recipe.
Do not submit this to LocalMaxxing because it is a quality sanity run with no
new performance result.

## Artifacts

- Quality JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/promoted-env-guard-sanity-20260521T114421Z/minimax-promoted-env-guard-raw145-n64.json`
- Quality log:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/promoted-env-guard-sanity-20260521T114421Z/minimax-promoted-env-guard-raw145-n64.log`
- Summary data:
  `data/minimax-m27-promoted-env-guard-sanity-20260521.json`
