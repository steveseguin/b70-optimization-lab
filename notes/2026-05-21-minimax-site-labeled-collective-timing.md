# MiniMax M2.7 Site-Labeled Collective Timing - 2026-05-21

## Goal

Temporarily add no-math-change `allreduce_label` scopes around MiniMax and MoE collective call sites to split the promoted decode timing buckets by source.

The labels were added only for this diagnostic run and removed afterward from both:

- `/home/steve/src/vllm`
- `/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/vllm`

## Quality Gate

Before using the timing data, the labeled runtime ran the raw145 exact-token canary:

- Prompt: `prompts/minimax-raw145-tokenhash-canary.txt`
- Output tokens: `64`
- Expected combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Observed combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Passed: `true`
- Degenerate/control/NUL checks: passed

The timing labels therefore did not alter the sampled output. The labels were removed after the probe and `py_compile`/import checks passed.

## Timing Probe

Warm vLLM random-text probe:

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM XPU, TP4, llm-scaler WS INT4 path
- Prompt/output: 512 prompt tokens, 512 output tokens
- Warmup/measured: 1 warmup, 1 measured repeat
- Decode throughput: `95.28611507903615` tok/s
- Total throughput: `190.5722301580723` tok/s
- Token SHA256: `d68667b0486b29b562aae054ff2b4d422d363f37b1dbed2d85b8a264a08b047b`

Largest rank-0 timing buckets with `VLLM_XPU_DECODE_TIMING_SYNC=0`:

- `all_reduce:minimax.moe.output_inside_custom_op:(2, 3072):torch.float16`: `650.618192 ms` total, `108` calls, `6.024243 ms` average
- `all_reduce:(2, 2):torch.float32`: `604.367179 ms` total, `108` calls, `5.595992 ms` average
- `all_reduce:(2, 3072):torch.float16`: `493.679216 ms` total, `110` calls, `4.487993 ms` average
- `all_reduce:(1, 2):torch.float32`: `435.800759 ms` total, `170` calls, `2.563534 ms` average
- `all_reduce:(1, 3072):torch.float16`: `415.876388 ms` total, `173` calls, `2.403910 ms` average
- `all_reduce:minimax.moe.output_inside_custom_op:(1, 3072):torch.float16`: `165.536663 ms` total, `170` calls, `0.973745 ms` average
- `logits.local_argmax_lm_head`: `66.437850 ms` total, `1010` calls, `0.065780 ms` average
- `gpu_model_runner.async_output_tolist`: `2.049628 ms` total, `1008` calls, `0.002033 ms` average

## Interpretation

The labeled MoE output all-reduce is a real, visible part of decode cost, but it is not the only limiter. The unlabeled `(1 or 2, 2)` FP32 buckets are still the Q/K variance collectives. The unlabeled `(1 or 2, 3072)` FP16 buckets are likely attention `o_proj` and other compiled hidden-state all-reduces whose Python labels do not survive the compiled graph boundary.

Approximate non-synchronized rank-0 attribution for the main decode buckets:

- Q/K variance collectives: about `1040 ms` total across `(2, 2)` and `(1, 2)`.
- Unlabeled FP16 hidden-state collectives, likely attention `o_proj` family: about `910 ms` total across `(2, 3072)` and `(1, 3072)`.
- Labeled MoE output collectives: about `816 ms` total across labeled `(2, 3072)` and `(1, 3072)`.

These timings are relative signals, not exact kernel durations, because `SYNC=0` avoids explicit synchronization. They are still enough to rule out CPU output callbacks and to show there is no single trivial callback win left.

## Decision

Diagnostic only. No LocalMaxxing submission.

Next optimization work should target math-preserving reductions in this order:

1. MoE output all-reduce scheduling/fusion, because it is now explicitly labeled and visible.
2. Attention/row-parallel hidden-state all-reduce reduction or scheduling, because Python labels do not survive the compiled path and prior wrapper-only attempts did not help.
3. Q/K tiny variance collective alternatives only behind exact-token gates, because prior Q/K AR/apply attempts were neutral or quality-negative.

## Artifacts

- Quality JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/site-labeled-promoted-20260521T025138Z/minimax-site-labeled-promoted-raw145-n64.json`
- Quality log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/site-labeled-promoted-20260521T025138Z/minimax-site-labeled-promoted-raw145-n64.log`
- Warm timing JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/site-labeled-promoted-warm-20260521T025808Z/minimax-site-labeled-promoted-warm-vllm-random-text-p512n512.json`
- Warm timing log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/site-labeled-promoted-warm-20260521T025808Z/minimax-site-labeled-promoted-warm-vllm-random-text-p512n512.log`
- Summary data: `data/minimax-m27-site-labeled-collective-timing-20260521.json`
