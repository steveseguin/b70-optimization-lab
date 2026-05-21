# MiniMax M2.7 Router Custom-Op Boundary Neutral Result - 2026-05-21

## Goal

Test whether moving the MiniMax router linear projection into the llm-scaler
MiniMax MoE custom-op boundary reduces framework/CPU scheduling overhead during
decode, without changing routing semantics or model quality.

The candidate added a new llm-scaler entry point:

`moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_router`

The wrapper computes:

1. `router_input = x.to(torch.float32)`
2. `router_logits = router_input @ gate_weight.T`
3. the existing MiniMax logits work-sharing INT4 MoE path

This preserves the same FP32 router logits and then feeds the same existing
MiniMax MoE WS path. It is intentionally not a router/top-k approximation.

## Quality Gate

The candidate passed exact token-hash canaries before throughput was considered:

- raw145 n64 expected SHA256:
  `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n64 observed SHA256:
  `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 expected SHA256:
  `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- raw145 n256 observed SHA256:
  `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- Deterministic across selected runs: `true`
- Failure reasons: none

An eager path-proof run also confirmed the candidate actually selected the new
router custom-op during decode on all four XPUs:

`[minimax-router-custom-op] shape=(1, 3072) device=xpu:{0..3} dtype=torch.float16`

## Throughput

Warm in-process p512/n1536 run, TP4, ctx2048, batch 1:

- Candidate mean output: `92.83189777020272` tok/s
- Candidate mean total: `123.77586369360363` tok/s
- Candidate output stdev: `0.024858108519755014`
- Candidate repeats:
  `92.85620991659901`, `92.82976590683394`,
  `92.79831130792165`, `92.84330394945627`

Restored promoted active control from the same post-reboot stack:

- Control mean output: `92.85479750507976` tok/s
- Control mean total: `123.80639667343968` tok/s
- Control output stdev: `0.040026329163842786`
- Control repeats:
  `92.7992391363912`, `92.8518588965701`,
  `92.8839952146276`, `92.88409677273015`

Delta versus the restored promoted active control:

- Output delta: `-0.02289973487704` tok/s
- Relative delta: about `-0.025%`

## Decision

Reject as a speed optimization. This is quality-clean but neutral to slightly
negative, so it should not be promoted and should not be submitted to
LocalMaxxing.

The result is still useful: it proves that simply moving the FP32 router linear
matmul into a Python-visible custom-op boundary is not the remaining bottleneck.
Future router/MoE work needs a lower-level optimized router/top-k/MoE fused
kernel or should focus elsewhere.

## Artifacts

- n64 quality JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/router-customop-forced-quality-20260521T052234Z/minimax-router-customop-forced-raw145-n64.json`
- n256 quality JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/router-customop-forced-quality-n256-20260521T054240Z/minimax-router-customop-forced-raw145-n256.json`
- eager path-proof JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/router-customop-eager-pathproof-20260521T054001Z/minimax-router-customop-eager-pathproof.json`
- eager path-proof log:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/router-customop-eager-pathproof-20260521T054001Z/run.log`
- warm throughput JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/router-customop-forced-warm-20260521T054825Z/minimax-router-customop-forced-warm-p512n1536.json`
- summary data:
  `data/minimax-m27-router-customop-neutral-20260521.json`
