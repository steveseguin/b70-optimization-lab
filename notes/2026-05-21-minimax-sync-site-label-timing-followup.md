# MiniMax M2.7 Sync Site-Label Timing Follow-Up - 2026-05-21

## Goal

Use no-math-change timing labels around MiniMax collective call sites to identify
which reductions still matter after the promoted 4x B70 vLLM/XPU path reached
strict-quality `89.314 tok/s` public decode and `92+ tok/s` warm in-process
decode.

This follow-up used `VLLM_XPU_DECODE_TIMING_SYNC=1` in eager mode so timing
buckets are easier to interpret than the earlier graph-mode, non-synchronized
probe.

## Result

Eager timing is slow overall, but it makes the per-call collective costs clear:

- MoE output all-reduce, decode shape `(1, 3072)` FP16:
  `0.090169 ms` average over `7874` calls.
- Attention `o_proj` all-reduce, decode shape `(1, 3072)` FP16:
  `0.087192 ms` average over `7874` calls.
- Q/K variance all-reduce, decode shape `(1, 2)` FP32:
  `0.081110 ms` average over `7874` calls.

The largest total timing bucket is still `minimax.moe.experts_total`, not one
single collective label. This means the next large win probably has to reduce
multiple per-layer decode boundaries or make the MoE expert kernel itself
cheaper; simply shaving one labeled all-reduce is unlikely to produce a
step-change.

## Decision

Diagnostic only. No LocalMaxxing submission.

Useful next targets:

1. Lower-level MoE expert/router fusion, because `experts_total` dominates.
2. Combined scheduling across MoE output, attention output, and Q/K variance
   reductions, because each contributes a similar per-layer decode cost.
3. Avoid CPU/framework callback work only when the candidate can prove both
   exact token hashes and a material p512/n1536 warm speedup.

## Artifacts

- Graph timing log:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/site-label-timing-20260521T092719Z/minimax-site-label-sync-timing-p512n256.log`
- Graph timing JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/site-label-timing-20260521T092719Z/minimax-site-label-sync-timing-p512n256.json`
- Eager timing log:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/eager-site-label-timing-20260521T093335Z/minimax-eager-site-label-sync-timing-p512n64.log`
- Eager timing JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/eager-site-label-timing-20260521T093335Z/minimax-eager-site-label-sync-timing-p512n64.json`
- Summary data:
  `data/minimax-m27-sync-site-label-timing-followup-20260521.json`
