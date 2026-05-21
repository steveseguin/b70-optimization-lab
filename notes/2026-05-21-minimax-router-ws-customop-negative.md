# MiniMax M2.7 Router+WS Custom-Op Negative Result - 2026-05-21

## Goal

Test a stricter version of the router custom-op idea: compute the exact FP32
MiniMax router logits inside a new llm-scaler C++ entry point, then immediately
call the existing work-sharing MiniMax INT4 MoE path.

Candidate entry point:

`moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_router_ws`

The candidate preserves quality intent:

1. Convert hidden states to FP32.
2. Compute `router_logits = hidden_states_fp32 @ gate_weight.T`.
3. Feed those logits into the existing MiniMax logits WS INT4 MoE kernel.

No top-k approximation or quantized router shortcut is used.

## Quality Gate

The candidate passed the full strict gate before benchmarking:

- raw145 n64 exact hash:
  `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact hash:
  `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite hash:
  `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic repeat hash:
  `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack hash:
  `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

The first debug attempt failed before validation because a Python `print` inside
the compiled model path caused a TorchDynamo graph break. The debug print path
was removed; the no-debug candidate then passed.

## Throughput

Matched warm p512/n1536 screen, TP4, ctx2048, batch 1, same rebuilt llm-scaler
package:

- Candidate mean output: `92.27838026827611` tok/s.
- Candidate mean total: `123.03784035770147` tok/s.
- Candidate stdev: `0.005066630819544155`.
- Control mean output: `92.415143036347` tok/s.
- Control mean total: `123.22019071512935` tok/s.
- Control stdev: `0.03345485385035345`.
- Delta: `-0.13676276807089494` tok/s, about `-0.148%`.

The previous promoted warm control from the active stack was also higher at
`92.83821084989822` tok/s, so this is not an improvement.

## Decision

Reject as an optimization. It is quality-clean but slightly slower, so it is not
promoted and was not submitted to LocalMaxxing.

The result is useful because it rules out a pure Python-boundary move for the
exact router+MoE WS path. A future router win likely needs a lower-level fused
router/top-k/dispatch kernel or a different MoE expert scheduling strategy, not
just moving exact FP32 router matmul into the same custom-op boundary.

## Artifacts

- Strict quality summary:
  `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-router-ws-customop-nodebug-quality-20260521-strict-tp4-ctx2048-mbt512-bs256-20260521T095125Z-summary.json`
- Candidate warm JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/router-ws-candidate-paired-20260521T100852Z/minimax-router-ws-candidate-warm-p512n1536.json`
- Control warm JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/router-ws-candidate-paired-20260521T100852Z/minimax-router-ws-control-warm-p512n1536.json`
- Isolated candidate workspace:
  `/mnt/fast-ai/src/llm-scaler-router-ws-20260521T094408Z/vllm/custom-esimd-kernels-vllm`
- Summary data:
  `data/minimax-m27-router-ws-customop-negative-20260521.json`
