# MMVQ + residual + RMSNorm + Q8_1 fusion boundary

Date: 2026-07-12

## Objective

Remove the standalone RMSNorm submission and the normalized FP32 activation
write/read between a fused projection-residual update and the next MMVQ
projection. This is a guarded experiment, not a promoted default.

## Implementation

The source experiment adds `GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8`, default `0`.
It must be enabled together with `GGML_SYCL_FUSE_MMVQ_ADD=1`.

The graph matcher accepts only this exact sequence:

1. an MMVQ projection accepted by the existing MMVQ+ADD matcher;
2. its residual `ADD` output;
3. a single-consumer contiguous F32 `RMS_NORM`;
4. an elementwise `MUL` by the learned contiguous F32 norm
   weight, whose element count is exactly the hidden width;
5. optional alias-preserving metadata nodes;
6. one to three following device-local MMVQ projections using that normalized
   and weighted value as `src1`, with the graph use count exactly matching the
   discovered consumer list and a common Q8_1 layout.

For an accepted sequence, the existing MMVQ epilogue writes the residual sum.
The RMSNorm node is skipped. During the next MMVQ's activation preparation, a
single fused kernel reads the residual sum, computes one RMS scale per row,
applies the learned norm weight per channel, and writes either standard or
reordered Q8_1 blocks directly into the skipped norm-MUL tensor's fixed-address
F32 allocation. That allocation is larger than the Q8_1 payload and remains
live through the last graph consumer. The first projection produces Q8_1;
later gate/up or Q/K/V projections reuse the exact same bytes without another
quantization launch. Neither the normalized nor weighted F32 tensor is
materialized, and no allocation occurs during graph capture.

The boundary therefore replaces three submissions (RMSNorm, norm-weight MUL,
and Q8_1 quantization) with one and removes both full-width F32 intermediates
per row. It does not claim to combine the global RMS reduction into the
preceding projection kernel; that would require cross-workgroup
synchronization.

Power-of-two counters report eligible, fused, and rejection-reason totals with
the `MMVQ+ADD+RMS+Q8` prefix. Unsupported shapes, multiple consumers,
observable RMS/MUL outputs, broadcast patterns other than one exact hidden-size
weight vector, split/non-device buffers, non-contiguous layouts, mixed
standard/reordered consumers, scratch overlap/capacity failures, and non-MMVQ
consumers retain the ordinary RMSNorm, MUL, and quantization path.

## Validation gates

The implementation was left for the manager-owned consolidated build and GPU
run. Before promotion:

1. build the guarded source and run `git diff --check`;
2. show nonzero eligible and fused counters on the Qwen 27B decode graph;
3. compare deterministic graph-off output with both fusion flags off and on,
   including a recurrent multi-token case and M=1/4 verifier widths;
4. inspect rejection counters to quantify actual layer coverage;
5. profile submissions and device time to prove one launch is removed per
   accepted boundary;
6. require a strict cold-suite throughput win before enabling the flag in a
   promoted launcher.

## Risks

- The combined kernel performs the RMS reduction in the same subgroup/tree
  shape as the existing large-row RMSNorm kernel, but floating-point operation
  ordering and the absence of the intermediate F32 store can still alter edge
  rounding at Q8 bin boundaries. Output parity is mandatory.
- Transparent metadata is accepted only when it preserves the same pointer,
  element count, type, and contiguous layout and has one consumer.
- The current Q8 scratch allocation remains per projection invocation. This
  change removes activation traffic and one kernel submission, not allocation
  or full-decoder persistence overhead.
- The current experimental MMVQ+ADD plumbing routes the ordinary MMVQ entry
  through the epilogue-capable dispatcher with a null epilogue. Its supported
  Q4/Q5 device kernels therefore still carry a runtime nullable residual
  argument/predicate in the baseline binary. Restoring compile-time-separated
  baseline and residual epilogue kernel instantiations is a required follow-up;
  it was not mixed into this boundary patch because doing it correctly touches
  every Q4_0/Q4_1/Q5_K single- and multi-column reorder dispatcher.
