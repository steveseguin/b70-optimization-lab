# Laguna exact M12 mapped gather 192x16 geometry preregistration

Date: 2026-08-01 America/Toronto

Status: **closed exact component-positive below the absolute gate**. The
192x16 kernel was exact 6/6 and `1.650228x` faster than its matched control,
but the extrapolated `0.249288 ms/cycle` saving missed `0.30 ms/cycle`.

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

## Result

Candidate source is
`4174a071690fc164823c90d29f29c8b98dae423a`. The sealed `_moe_C.abi3.so`
has SHA-256
`6c23b5b03cc489c58b3c0d3693777808827cfce44cf5ea40596023c3701c5c88`
under
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/builds/m12-mapped-gather-192x16-4174a07/package`.
The incremental build completed in 47.88 seconds with 1,113,716 KiB maximum
RSS and zero swaps. It emitted only the same unrelated TopKGating spill
warnings as the parent build; the treatment emitted no spill warning.

The unchanged component gate passed all six raw-BF16 comparisons, including
remote `-1` maps before and after timing, and all inputs remained immutable:

| scope | median |
| --- | ---: |
| generic mapped gather + M12 scale/add | 0.013180700 ms |
| fused 192x16 mapped gather/scale/add | 0.007987200 ms |
| component speedup | **1.650228x** |
| extrapolated 48-layer saving | **0.249288 ms/cycle** |

The 192x16 treatment made the fused kernel 8.53% faster than the preceding
256x8 candidate, but its matched control was also faster in this first valid
leg. Net saving missed the unchanged absolute gate by `0.050712 ms/cycle`.
The first result stands; there was no retry, integration, topology smoke,
model run, or LocalMaxxing action.

This closes geometry-only tuning of the exact mapped gather fusion for
endpoint use. Both tested geometries are exact and strongly faster relatively,
but the whole tail is too small to satisfy the conservative absolute gate.
Do not rerun for favorable noise or integrate by relaxing that gate. A future
tail treatment must remove additional real work beyond this same boundary.

Raw result:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/m12-mapped-gather-192x16-component-4174a07-20260801T094000Z/summary.json`.
