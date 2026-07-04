# 2026-07-04 - Qwen27 LM-head upper bound and priority correction

## Scope

This note corrects the post-explorer ranking for the current Qwen27 record
lane:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- mode: AutoRound W4A16 + runtime INT8 LM-head with BF16 scales;
- record to beat: `65.27648650325429 tok/s`, LocalMaxxing
  `cmr5iu3gk00bfq901nidgcana`;
- strict policy: fixed Qwen realistic suite, fresh one-shot prompts,
  `cached_tokens=0`, target-verified MTP.

The correction: a **target-only lazy verifier** is technically valid but too
small to be the first expensive implementation lane. The draft LM-head calls
are the larger avoidable bucket.

## Inputs

Timing artifact:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-phase1-timing-summary-20260704T020549Z.json
```

Acceptance artifact:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-specaccept-trace-summary-20260704T032236Z.md
```

Recorded timing facts:

- `2258` LM-head/logits calls over `540` verifier steps;
- `lm_head_int8.gemm_w8a8` total `5729.193765 ms`;
- average LM-head GEMM call `2.5372868756 ms`;
- LM-head GEMM cost per verifier step `10.6096180833 ms`;
- draft greedy LM-head calls: `1684`, about `7.9125761082 ms/step`;
- target verifier LM-head calls: `540`, about `2.5372868756 ms/step`.

Recorded acceptance:

- emitted tokens per step: `2.6973451327`;
- per-position acceptance: `p0=0.7840707965`,
  `p1=0.5592920354`, `p2=0.3805309735`;
- full-accept rate: `0.3805309735`.

## Target-only lazy verifier upper bound

For exact greedy MTP3 target verification, a conditional verifier would need:

```text
row0 always
row1 if p0 accepted
row2 if p1 accepted
bonus row if p2/full accepted
```

Expected target rows:

```text
1 + 0.7840707965 + 0.5592920354 + 0.3805309735 = 2.7238938053 rows
```

If a native op made target row cost scale perfectly linearly:

```text
2.7238938053 / 4 = 0.6809734513 of current target rows
target LM-head save = 2.5372868756 ms * (1 - 0.6809734513)
                    = 0.8094618749 ms/step
```

Using the current record-family throughput as the step-time anchor:

```text
current approx step time = 1000 * 2.6973451327 / 65.2764865033
                         = 41.3218492176 ms/step
target-only save estimate -> ~66.58 tok/s
```

That is a best-case `~2%` movement before variance, implementation overhead,
graph constraints, and exact tie/padding behavior. It is useful only as a later
cleanup or if it is fused into a broader top-ID producer.

## Larger levers

Estimated throughput if step-time savings were achieved without changing
accepted tokens/step:

| Step saving | Rough tok/s |
| ---: | ---: |
| `0.81 ms` | `~66.58` |
| `3 ms` | `~70.39` |
| `5 ms` | `~74.26` |
| `8 ms` | `~80.95` |
| `10.61 ms` (all LM-head GEMM cost) | `~87.83` |

This means:

1. a target-only lazy verifier is not enough;
2. a true top-ID producer must help **draft and target** greedy LM-head calls;
3. accepted-token improvement is still the route to larger jumps because even
   deleting all measured LM-head GEMM cost does not reach Gemma-like rates.

## Current source observation

The existing MoE `topk8` grouped-GEMM code in
`/home/steve/src/vllm-xpu-kernels/csrc/xpu/grouped_gemm/xe_2/` is not a ready
LM-head primitive. It is specialized around expert routing / top-k expert
selection and dense expert-intermediate outputs, not full-vocab argmax emission
for `[rows <= 4, hidden=5120, vocab=248320]`.

The preserved compact LM-head top-1 prototype remains the relevant negative
result:

```text
experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-compact-lmhead-top1-kernel-no-win.md
patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lmhead-compact-top1-n64-no-win-20260704.patch
```

## Corrected priority

Do next:

1. **Top-ID producer for all greedy LM-head calls**: a oneDNN/XPU-class
   primitive behind `get_top_tokens()` that returns exact IDs/values and helps
   the three draft calls plus the target call.
2. **Target-matched drafter calibration/training** on held-out
   realistic-style data, with exact target verification and no final-suite
   leakage.

Do later or only as part of a larger primitive:

3. target-only lazy verifier row skipping.

Do not repeat:

- Python rows-1 lazy verification;
- scheduler-only adaptive depth;
- partial-group dynamic depth without full metadata/GDN/graph support;
- standalone full-vocab top-1 kernels that still require a second reduction
  launch and lose to oneDNN.

