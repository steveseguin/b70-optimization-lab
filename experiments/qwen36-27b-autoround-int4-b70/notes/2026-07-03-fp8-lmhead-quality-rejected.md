# 2026-07-03 FP8 LM-head quality rejection

## Summary

The experimental XPU FP8 LM-head path is rejected for the primary Qwen3.6 27B
AutoRound INT4 lane. It produced a large strict short-suite speedup, but failed
the full quality gate against the current baseline, specifically the 1K
long-context needle case.

This is a useful diagnostic result, not a headline or LocalMaxxing result.
Do not submit it as the same-quality `Intel/Qwen3.6-27B-int4-AutoRound`
configuration.

## Patch

Preserved patch:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-fp8-quality-fail-20260703.patch
```

The patch added a default-off `VLLM_XPU_LM_HEAD_FP8=1` path in
`vllm/model_executor/layers/vocab_parallel_embedding.py` that:

- kept the original BF16/FP16 `lm_head.weight` intact;
- built transient per-output-channel FP8 weights for `_xpu_C.fp8_gemm_w8a16`;
- used `VLLM_XPU_LM_HEAD_FP8_DTYPE=e4m3fn` in the tested lane.

The active source tree was reverted after preserving the patch.

## Why It Was Tried

Timing on the promoted MTP3 recipe showed LM-head/logits as the dominant cost:

- `spec_decode.greedy_sample.compute_logits`: about `4.45 ms`;
- `gpu_model_runner.compute_logits`: about `4.42 ms`;
- proposer model forward: about `0.65-0.83 ms`.

A synthetic single-row microbench on B70 showed:

- BF16 `F.linear`: about `4.49 ms`;
- FP8 W8A16 projection: about `2.24 ms`;
- FP8 W8A16 projection + argmax: about `3.72 ms`.

That made the path worth a quality-gated screen, but it changes LM-head
numerics and was never semantics-preserving.

## Results

Quality smoke passed:

```text
data/qwen36-27b-autoround-int4-b70-baselines/quality-fp8lmhead-smoke-20260703T130747Z.json
```

Strict fresh short-suite throughput passed and was fast:

```text
data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-fp8lmhead-realistic128-chat-tokenids-qwensuite-20260703T130926Z.json
median_tok_s_1_100_after_ttft = 64.82432326975983
p10_tok_s_1_100_after_ttft    = 57.79942561377245
mean_tok_s_1_100_after_ttft   = 65.13628825647508
cached_tokens_all_zero        = true
passed                        = true
```

Full quality failed:

```text
data/qwen36-27b-autoround-int4-b70-baselines/quality-fp8lmhead-mtp3-cg8-repeat32-ctx1024-20260703T131329Z.json
baseline_match_all = false
pass_all           = false
```

Failure signature:

```text
long_context:same_hash = false
long_context:same_pass = false
long-context output    = B!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
cached_tokens          = 0
```

Short exact cases and repeat hash stability matched the baseline, but the
long-context failure is sufficient to reject the lane under the no-quality-loss
rule.

## Decision

- Rejected for headline throughput and LocalMaxxing.
- Keep as a negative patch/result because it quantifies the LM-head opportunity.
- Future LM-head work should preserve BF16 target semantics, for example a true
  exact top-1/candidate-bound verifier kernel, rather than changing LM-head
  precision.
