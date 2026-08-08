# The native-MM attention path is exact, reachable, and has no demonstrated win

Date: 2026-08-07 America/Toronto

Status: **closed as no demonstrated endpoint win. The latest one-point A/B is
2.8% slower, while the earlier stronger multi-prompt endpoint evidence was
0.243% faster and explicitly below noise. Exactness is validated.**

## What was found

`_xpu_apply_batched_m1_method` presents each verifier row to oneDNN as a
stride-zero BMM, which is the mechanism that keeps a row's arithmetic
independent of the batch it rides in. Immediately above it sits a faster branch
that issues a plain `torch.mm` instead -- gated, among other things, on

```python
and rows.shape[0] == 8
```

This campaign runs a **width-12** verifier. The branch was therefore
unreachable, and `VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM` did nothing whatever it was
set to. The harness pinned it to 0 with no way to raise it, which was
reasonable while it could not fire.

Its shape set -- `(3072, 2048)`, `(1536, 3072)`, `(3072, 2816)`,
`(2304, 3072)` -- is already exactly the target and drafter qkv/o projections at
TP4. So the width was the only thing between the selector and the **96
stride-zero BMMs the verifier issues per decode step**.

## The exactness precondition, tested against the right reference

The invariant this campaign rests on is not "the two batched forms agree with
each other". It is that **a verifier row produces what that row would have
produced alone**, because otherwise speculation changes the emitted token. So
the reference is a row computed by itself:

| M | shape | stride-zero BMM vs alone | `torch.mm` vs alone |
| ---: | :--- | :--- | :--- |
| 8 | all four | bitwise equal | **bitwise equal** |
| 12 | all four | bitwise equal | **bitwise equal** |

Random BF16 inputs, 16 trials per shape, on the XPU.

## And then confirmed on the served path

The A/B below emitted **bitwise-identical token streams** -- same
`output_token_ids_sha256`, same `token_ids` -- on both cases, with the selector
the only difference. That is a much stronger statement than the synthetic
check: the fast path is exact in the real model, through 48 layers and a
drafter, not merely on isolated shapes.

## The measurement

Both legs sealed, `original_status=0`, q12, width 12, TP4, EP4, util 0.80.

| case | selector off | selector on | delta | tokens |
| :--- | ---: | ---: | ---: | :--- |
| 1,024 middle | **156.60** | 152.21 | **-2.8%** | identical |
| 1,024 early (cold) | 8.43 | 8.39 | -0.5% | identical |

This latest warm point is **2.8% slower**. It is a valid observation, but one
point does not establish a general kernel ordering.

The earlier 13-prompt exact endpoint experiment recorded native MM at
`+0.2427%`, explicitly below its noise floor, after 224/224 raw and streamed
component comparisons passed. Taken together, the supported conclusion is
that native MM is exact and has **no demonstrated endpoint win**, not that it
is universally slower.

## Why, and what it means for the wider hypothesis

The shapes are extremely skinny: a 12x3072 activation against a 3072x2048
weight. The latest point is consistent with the stride-zero BMM mapping better
on that run, but the prior near-zero result prevents promoting that explanation
to a measured general fact.

That matters beyond this selector. The downgraded py-spy note
([2026-08-05](2026-08-05-the-m1-linear-path-is-the-serving-path-cost.md))
suggested the M=1 linear path was where the serving-path time went. Replacing
the stride-zero BMM with a plain matmul has not recovered endpoint time in
either measurement. That specific optimization is therefore not supported,
without claiming a universal ranking between the two kernels.

## What was changed anyway, and why it should stay

The width gate now tracks `xpu_laguna_exact_max_m()` rather than the literal 8
(`561698049`), and the selector is reachable from the harness (`f306c0027`).
Width 8 admits exactly what it admitted before. Both are worth keeping even
though the answer is negative: the branch was dead code that looked live, and
the next person to read it would have drawn the same hypothesis and paid the
same measurement to disprove it.

The selector remains **default-off**.

## Boundaries

`20260807-attnmm-base` and `20260807-attnmm-attnmm`, differing only in
`LAGUNA_ATTN_MM`. Both sealed with runner exit 0 and benchmark status
`PASS_BASELINE_ORACLE_NOT_TESTED`, cold prefix cache on every row, captured
topology 146/145 target plus 14/13 drafter on all four ranks. Decode figures are
`conventional_99_interval_first_100_tok_s`. The first case of each leg is a
throwaway that absorbs graph capture. No quantisation change. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
