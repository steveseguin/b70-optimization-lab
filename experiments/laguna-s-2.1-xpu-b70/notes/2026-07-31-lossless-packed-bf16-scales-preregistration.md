# Laguna lossless packed-BF16 scale records preregistration

Date: 2026-07-31 America/Toronto

Status: **closed exact component negative**. The candidate was exact 6/6 but
measured `0.994250x` the promoted component and stopped before integration.

## Checkpoint evidence and premise

The exact M12 target grouped GEMMs are bandwidth-dominated and move INT4
weights plus one BF16 scale per 32 weights. Arithmetic, scheduler, tile,
prefetch-distance, and scale-fold/MAD treatments are heavily closed. The
remaining precision-preserving byte source is the representation of the BF16
scale itself.

A read-only full scan of the promoted INT4 checkpoint inspected all
36,096 expert scale tensors and all 3,548,381,184 BF16 values:

- every scale is positive;
- 29,357 tensors span two high bytes;
- 6,641 span three high bytes;
- 45 span four high bytes;
- only 53 tensors span more, almost all layer-1 gate/up tensors containing
  near-zero outliers.

Thus the common path can store every exact BF16 bit pattern as its low byte
plus a two-bit delta from a local high-byte base. The first component uses
fixed 32-scale records in transposed `[group,N]` order:

- 32 low bytes;
- eight bytes containing four two-bit high-byte deltas each;
- one high-byte base;
- total 41 bytes versus 64 bytes of BF16, a 35.94% scale-byte reduction.

The packed record reconstructs the original 16-bit BF16 word before the
existing BF16 scale multiply. It is not FP8, requantization, approximation,
scale folding, or changed arithmetic. A record whose high-byte span exceeds
three must fail closed; production integration, if later authorized, must
retain ordinary BF16 for exceptional layers rather than alter any value.

The packed scale share bounds total INT4+scale traffic reduction near 4%.
This does not alone project 130 tok/s, but it is the only current exact
bandwidth treatment with checkpoint-wide evidence and can combine with later
independent wins.

## Candidate and gates

1. Start from protected kernel source `99886d783372e621941228250091dc8ebdc1595d`.
   Add a default-off, exact-M12/transposed-scale-only selector and separately
   named 128-GRF kernel. Selector off must retain the promoted path.
2. The component harness packs the same logical BF16 corpus into the 41-byte
   records for treatment only. Both arms use one DSO and identical logical
   weights, scales, rows, and changed inputs. The physical tensor may retain
   its original BF16 allocation/shape while only the packed prefix is read.
3. Retain the scale lookahead prefetch. The packed candidate may prefetch a
   covering cache line for each 32-scale record; disabling scale prefetch is
   forbidden because the exact no-prefetch treatment measured `0.687432x`.
4. Static BMG inspection must retain 128 GRFs, the exact two-DPAS/32-BF16-mul
   body, and the incumbent persistent scheduler. It must show a distinct
   reconstruction path and no unexpected arithmetic substitution.
5. On one idle B70, require 6/6 raw-BF16 equality under 200 warmups and 15x40
   timing, no per-shape regression, and at least `1.025x` summed W13+W2
   speedup. Stop and preserve below that threshold.
6. A component pass authorizes only load-time pack integration plus host
   packing tests and a four-rank topology smoke. Exceptional layer/tensor
   behavior must fail closed to ordinary BF16. Smoke must retain cache zero,
   146/145 target, 14/13 draft, normal acceptance, and clean teardown.
7. Only a passed smoke authorizes one cold frozen 13-prompt endpoint leg. The
   first valid result stands.

No model value, target/draft/KV precision, BF16 KV, width/depth, verification,
sampling, prompt, teacher, cache policy, metric, retry, warm generation,
capture window, or scoring window may change. No reboot, reset, FLR, driver
reload, or privileged recovery is authorized.

## Result

Candidate kernel source is
`a0b6ed99b2e60660d2bd0abb6feff5d5317094bb`. The sealed DSO is
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/builds/lossless-packed-scales-a0b6ed9/libgrouped_gemm_xe_2.so`
with SHA-256
`3282609370b8c85ddf2b93b0c763775b543f52bd2d10271da6bfd3d5fe835298`.
The incremental production build completed in 16:43.56 with 106,825,448 KiB
maximum RSS and zero swaps.

Static BMG inspection found both the separately named packed-scale treatment
and its byte-path control in the same compile. Both retained 128 GRFs, 2 DPAS,
the persistent atomic/barrier topology, and no scratch/spill path. The control
retained 679 instructions; exact high-byte reconstruction raised the treatment
to 787 instructions. The additional 108 instructions are the cost the device
gate tested against the reduced scale traffic.

The frozen one-B70 component used one DSO for both arms, changed inputs, 200
warmups, 15 timing samples, and 40 launches per sample:

| shape | BF16 control | lossless packed scales | speedup |
| --- | ---: | ---: | ---: |
| W13 | 0.333258075 ms | 0.334758375 ms | 0.995518x |
| W2 | 0.177906700 ms | 0.179362425 ms | 0.991884x |
| sum | 0.511164775 ms | 0.514120800 ms | **0.994250x** |

All six raw-BF16 output comparisons were bitwise exact. The candidate missed
the preregistered `1.025x` gate and regressed both real shapes, so no model
packing, topology smoke, endpoint run, or LocalMaxxing action occurred.

This result closes per-use lossless scale reconstruction in the grouped-GEMM
mainloop in its tested 32-scale/41-byte form. Although it removes 35.94% of
the scale bytes, scales are only a small fraction of total INT4-plus-scale
traffic and the reconstruction executes in the hot loop. Do not infer that
fewer bytes are faster without pricing exact decode instructions in final ISA.
A future representation must demonstrate materially cheaper reconstruction in
static BMG before another production build; changing BF16 values or rounding
remains forbidden.

Raw result:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/lossless-packed-scales-component-a0b6ed9-20260801T091500Z/summary.json`.
