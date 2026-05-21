# MiniMax M2.7 Q/K Helper Fusion Current-Stack Negative - 2026-05-21

## Goal

Retest vLLM's `fuse_minimax_qk_norm` compiler pass on the current promoted
MiniMax stack, this time with the XPU helper module available on `PYTHONPATH`:

`/home/steve/llm-optimizations-publish/experiments/minimax_qk_rms_xpu`

The intent was to see whether the compiler pass could reduce the Q/K RMS
variance all-reduce overhead without changing model weights, quantization,
sampling, router precision, speculative decoding, or power limits.

## Screen

Warm in-process p512/n1536 screen, TP4, ctx2048, batch 1, block-size 256,
same promoted environment, fresh graph cache.

Relevant env/config additions:

- `VLLM_MINIMAX_QK_NORM_XPU_HELPER_FUSION=1`
- `PYTHONPATH=/home/steve/llm-optimizations-publish/experiments/minimax_qk_rms_xpu:$PYTHONPATH`
- `pass_config.fuse_minimax_qk_norm=true`

The log confirmed the pass was enabled:

`Enabled custom fusions: minimax_qk_norm`

## Result

- Mean output: `92.24376748272135` tok/s.
- Mean total: `122.99168997696181` tok/s.
- Stdev output: `0.09303536924265332`.
- Repeats: `92.112535394217`, `92.2918898949191`,
  `92.24675093877917`, `92.32389370297015`.

Recent matched controls on the same promoted family were higher:

- `92.415143036347` tok/s in the router+WS paired control.
- `92.42571144685999` tok/s in the default-after-shape-gate control.
- `92.83821084989822` tok/s in the earlier promoted paired control.

## Decision

Reject as an optimization. This was a warm speed screen only; because it did
not beat the controls, it was not advanced to the full strict quality gate and
was not submitted to LocalMaxxing.

The result does not invalidate the already-promoted Q/K direct in-place scale
work. It only says that enabling the current compiler-pass helper fusion on top
of the promoted stack is not a speed win. Future Q/K work likely needs a lower
level XPU/oneCCL fusion that truly combines peer reduction and RMS scaling,
rather than another compiler-boundary wrapper around the current helper.

## Artifacts

- Warm JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-helper-fusion-currentstack-warm-20260521T103851Z/minimax-qk-helper-fusion-currentstack-warm-p512n1536.json`
- Warm log:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-helper-fusion-currentstack-warm-20260521T103851Z/minimax-qk-helper-fusion-currentstack-warm-p512n1536.log`
- Summary data:
  `data/minimax-m27-qk-helper-fusion-currentstack-negative-20260521.json`
