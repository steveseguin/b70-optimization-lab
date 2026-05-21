# MiniMax M2.7 XPU Custom-Op Collectives Quality Fail - 2026-05-21

## Goal

Screen the upstream vLLM XPU collective-dispatch change as a config-only
candidate on the current promoted 4x B70 MiniMax stack. Upstream vLLM now
defaults XPU `use_custom_op_collectives()` to true; the local tree keeps it
behind an environment variable, so this test enabled:

`VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=1`

No model, quantization, sampling, router precision, speculative decoding,
driver, power, or quality-harness relaxation was used.

## Quality Gate

Rejected at the raw145 n64 exact-output gate.

- Passed: `false`
- Expected-token hash match: `false`
- Combined token SHA256:
  `242152df6909e5e25433f43875de5e51c210d146a22279611852b695bcf7d978`
- Expected token SHA256:
  `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Failure reasons:
  - `combined token hash mismatch`
  - `degenerate or corrupt generated output`

The generated tokens were quality-corrupt: one visible token followed by 63
NUL/control tokens. The harness also reported `disable_custom_all_reduce=false`,
confirming the environment switch materially changed the collective dispatch
path instead of being a no-op.

## Follow-Up Isolation

I reran the same raw145 n64 gate with the promoted tiny in-place FP32
collective disabled:

```
VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=1
VLLM_XPU_CUSTOM_ALLREDUCE_TINY_FP32_INPLACE_MAX_NUMEL=0
VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_MAX_NUMEL=0
```

That produced the same corrupt token hash and NUL/control output pattern:

- Combined token SHA256:
  `242152df6909e5e25433f43875de5e51c210d146a22279611852b695bcf7d978`
- NUL token count: `63`
- `disable_custom_all_reduce=false`

So the failure is not isolated to the tiny in-place FP32 micro-optimization;
the broader XPU custom-op collective dispatch path is unsafe on this local
stack.

## Decision

Reject. This is not a speed candidate because it corrupts deterministic output
before any throughput screen. Do not enable
`VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=1` on the current local stack unless the
underlying XPU custom collective implementation is repaired and exact-output
quality passes again.

The upstream change is still useful context: it shows where vLLM is moving, but
the current B70/Level Zero/XCCL/local patch combination is not safe with that
dispatch path.

## Artifacts

- Raw145 n64 failed quality JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/custom-op-collectives-quality-20260521T112122Z/minimax-custom-op-collectives-raw145-n64.json`
- Raw145 n64 failed quality log:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/custom-op-collectives-quality-20260521T112122Z/minimax-custom-op-collectives-raw145-n64.log`
- Out-of-place-only follow-up failed quality JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/custom-op-collectives-outplace-quality-20260521T112944Z/minimax-custom-op-collectives-outplace-raw145-n64.json`
- Out-of-place-only follow-up failed quality log:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/custom-op-collectives-outplace-quality-20260521T112944Z/minimax-custom-op-collectives-outplace-raw145-n64.log`
- Summary data:
  `data/minimax-m27-xpu-custom-op-collectives-quality-fail-20260521.json`
