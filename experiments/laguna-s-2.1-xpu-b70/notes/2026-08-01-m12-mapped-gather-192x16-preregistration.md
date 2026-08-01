# Laguna exact M12 mapped gather 192x16 geometry preregistration

Date: 2026-08-01 America/Toronto

Status: preregistered before source change, build, or device execution.

## Measured premise

The first exact mapped gather/scale/add fusion at source `defec37d4` passed
6/6 changed-input comparisons and improved the M12 tail from `0.014189500` to
`0.008732100 ms/layer` (`1.624981x`). It stopped because its extrapolated
`0.261955 ms/cycle` saving missed the frozen `0.30 ms/cycle` absolute gate.
The gap is `0.000793 ms/layer`.

That candidate uses 256 work-items and eight output elements per work-item.
Its 2,048-element stride requires two passes over hidden size 3,072; only 128
of 256 work-items are active in the second pass. The treatment changes only
the fused kernel geometry to 192 work-items and 16 elements per work-item.
The resulting 3,072-element stride covers the row in one pass with all 192
work-items active.

All input layouts, the real permutation map, remote `-1` skip, slot order,
FP32 accumulation order, and the routed/scaled/final BF16 helper remain
unchanged. The risk is increased register pressure from 16 accumulators; this
must be rejected statically if it spills.

## Gates

1. Build directly on `defec37d44526f55ab71287cabfe28251aad96c7` in the
   preserved candidate branch. Change only `GroupWorkItem` from 256 to 192
   and `ElemsPerItem` from 8 to 16 in
   `LagunaM12MappedGatherScaleAdd`; update the focused static test.
2. Production BMG compilation must emit the candidate without a spill or
   scratch warning. Existing unrelated TopKGating warnings are ignored only
   if byte-identical in kind to the preceding build.
3. Reuse the frozen component corpus, candidate package construction, control,
   200 warmups, alternating 15x40 timing, and thresholds without relaxation.
   Require 6/6 raw-BF16 equality, input immutability, at least `1.10x`, and at
   least `0.30 ms/cycle` extrapolated saving.
4. Stop and preserve if any gate fails. A pass authorizes only the integration,
   focused tests, and four-rank smoke described in the parent preregistration.
   It does not directly authorize an endpoint.

No arithmetic, model, INT4 weight, BF16 scale, BF16 KV, width/depth,
verification, sampling, prompt, teacher, cache, metric, retry, graph/scoring
window, or benchmark identity may change. No reboot, reset, FLR, driver
reload, or privileged recovery is authorized.
