# MoE scale folding: 8% faster, 0/13 exact, rejected

Date: 2026-07-28 America/Toronto

Status: **rejected.** `VLLM_XPU_LAGUNA_SCALE_FOLD` stays default-off.

## Result

Interleaved on one binary, so only the fold differs:

| arm | conventional tok/s | exact |
| --- | ---: | ---: |
| fold=1 | 109.185790 | **0/13** |
| fold=0 | 100.706829 | 13/13 |
| fold=1 | 107.609166 | **0/13** |
| fold=0 | 99.838748 | 13/13 |

About **+8%**, and every prompt wrong in both runs. More than enough speed to
clear 102, worth nothing.

## What it was

The mainloop applied the per-(N, K-group) scale to all 32 B elements per work
item per k-tile, feeding 2 DPAS issues. Because `tile_k == group_size`, the
scale can instead be applied once to the FP32 accumulator:
`sum_k a_k*(b_k*s) == s * sum_k a_k*b_k`. That removes about 24 of 32 scaling
instructions in the loop per-segment profiling puts at 69% of a verifier
forward. Kernel commit `0e1dee4`.

The implementation is sound. A GPU unit check over ten cases matched an FP32
reference at both settings, was bitwise identical to the unfolded path at
power-of-two scales, and the folded path measured **1.55x closer** to the FP32
reference than the unfolded one, since it skips rounding `b_k*s_n` back to
BF16.

## Why it still fails

The prediction that motivated the test was that greedy argmax would absorb a
small rounding change. It does not. The q=1 teacher was generated under the
unfolded rounding, so the contract is not "be numerically accurate", it is "be
identical to that path". A change that is *more* accurate is just as
disqualified as one that is less.

**This is the same shape as the draft-capture false wins** (198.7, 537.4,
550.9 tok/s at 0/13): on this stack, a large speedup that appears suddenly is
overwhelmingly likely to have broken the verifier's contract rather than found
free time. Check exactness before believing a number.

## What this closes

The largest structural lever identified in the whole campaign -- the dequant
instruction count in the 69% segment -- is unreachable while the teacher is
fixed. Reducing that cost requires either a transformation that provably
preserves the exact rounding sequence, or regenerating the teacher, which the
lane's contract forbids.

Remaining within the contract, from the kernel analysis: the 32 `apply_scale`
muls are separate inline-asm `mul (M1,16)` statements the compiler cannot
coalesce. A wider exec size or a vectorised BF16xBF16 form would cut the
instruction count **without changing the arithmetic or its order**, which is
the only version of this idea that can pass the gate.
