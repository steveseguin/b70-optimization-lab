# MiniMax M2.7 Q/K AR+Apply Custom Op Neutral Screen - 2026-05-21

## Goal

Test whether wrapping the Q/K RMS variance all-reduce, TP scale, and XPU apply helper behind one default-off opaque custom-op boundary improves steady-state decode throughput.

Candidate flag:

```bash
VLLM_MINIMAX_QK_RMS_AR_APPLY_CUSTOM_OP=1
VLLM_MINIMAX_QK_RMS_POST_AR_APPLY_CUSTOM_OP=0
```

The promoted environment was otherwise unchanged from `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`.

## Result

Warm text-prompt throughput screen:

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM XPU, TP4, llm-scaler WS INT4 path
- Prompt source: vLLM random text
- Prompt/output: 512 prompt tokens, 1536 output tokens
- Repeats: 4 measured after 1 warmup
- Mean decode: `92.36072395105047` tok/s
- Mean total: `123.14763193473397` tok/s
- Output tok/s range: `92.34870809302066` to `92.37201153894232`
- Output tok/s stdev: `0.011955306923006122`

Prior warm text baseline:

- Mean decode: `92.37491625407232` tok/s
- Mean total: `123.16655500542976` tok/s

## Decision

Rejected / not promoted.

The candidate is repeatable but very slightly slower than the existing promoted path, and it also caused a fresh torch.compile path with a long initialization time (`318.43 s` in this run). Because it did not produce a throughput win, no strict quality gate was run for promotion and no LocalMaxxing submission was made.

Quality posture: the promoted environment remains unchanged. This candidate is default-off and should not be used in the reproducible 89 tok/s setup unless retesting a future compiler/runtime stack.

## Artifacts

- Result JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-ar-apply-warm-20260521T020745Z/minimax-qk-ar-apply-warm-vllm-random-text-p512n1536.json`
- Log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-ar-apply-warm-20260521T020745Z/minimax-qk-ar-apply-warm-vllm-random-text-p512n1536.log`
- Summary data: `data/minimax-m27-qk-ar-apply-customop-neutral-20260521.json`
