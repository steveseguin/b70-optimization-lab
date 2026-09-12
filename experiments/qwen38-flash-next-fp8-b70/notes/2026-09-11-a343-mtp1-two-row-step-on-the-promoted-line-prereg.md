# Preregistration: A343 - the two-row (MTP1 verify) step on the promoted fused-QSA line

## Question

A340/A341 closed the MoE all-reduce question on the promoted MTP0 line: 27.2 ms per graph M=1 step
at exact-2K, and a zero-input all-reduce changes nothing. The remaining single-user term the lane
never re-measured after the September promotions is the two-row verify step. On the 09-03 line
(A127) the size-2 graph replay averaged ~181 ms against 71 ms at size 1, with MoE at M=2 costing
2.6x M=1 (A124/A125). What is the M=2 step on the promoted MTP1 line (`6d872457`: fused QSA,
Triton HC, placement, three exact-verify selectors) today?

## Arm

A343 = the promoted MTP1 packet A338 with `Q38_STEP_TIMING_LOG=10` and `Q38_MEM_NOTE=1` on the
diagnostic head `a402f97d3` (= `6d872457` + q38_timing helpers, step timing, memory note, event-sum
report; no all-reduce or skip hooks, which conflicted and are not needed here). Three exact-2K rows
through the depth harness. Outputs must equal the MTP1 line's authority for exact-2K (`afffd211…`,
the same as MTP0's by the lane's lossless MTP1 result).

## What is read

`Q38_STEP_TIMING` per step: `tokens=2` rows are the verify steps (one target forward over two rows,
then sampler, then the drafter); `draft_ms` is the MTP head. The verdict is the M=2 forward median
against A340's 27.2 ms M=1 and the drafter's share.

## Predictions

- If the two-row pathology was also the VRAM cliff: M=2 forward ~1.1-1.3x M=1 (30-36 ms), and the
  MTP1 line's remaining headroom is acceptance, not the step.
- If it persists: M=2 forward >= 2x M=1 (55 ms or more), and the next lever is the MoE M=2 path
  (per-expert grouped GEMM launches or the serial verifier-row GDN/QSA kernels), measured next by
  skip differencing on this head.

## Stop rules

- Any output hash != `afffd211…`: the diagnostic head changed numerics; stop.
- Preflight or health failure: stop and follow the post-fault rule.
