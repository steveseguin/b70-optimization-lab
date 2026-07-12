# Xe2 SIMD4 production MMVQ result

## Hypothesis

The active reordered Q4_0 x Q8_1 width-4 MMVQ loops over verifier columns
inside each weight-block iteration. An explicit width-4 specialization could
keep each Q4 block and scale live once while accumulating four activation rows,
reducing redundant load/address work in the MTP3 target verifier.

## Implementation

`/home/steve/src/llama.cpp` now contains an experiment-only width-4 kernel in
`ggml/src/ggml-sycl/mmvq.cpp`. It is guarded by
`GGML_SYCL_Q4_0_MMVQ_SIMD4=1` and defaults off. The existing reordered layout,
Q4_0 zero point, Q8_1 block layout, FP32 accumulation order, residual epilogue,
and output layout are unchanged. The exact-production benchmark hook accepts a
candidate selector so baseline and SIMD4 kernels can be timed in one process.

The isolated comparator is
`xe2-verifier/simd4-production-comparator.cpp`. It uses the real reordered
kernel and Q8_1 memory layout, alternates launch order, reports median device
event time over 50 iterations, and checks every output against baseline.

## Correctness

The JIT build completed. With the flag enabled, the focused SYCL backend test
passed every reordered width from 1 through 17. Width 4 selected the new
specialization. The production comparator reported `max_abs=0` for all three
real projection shapes.

## Performance

| M | K | N | Baseline kernel | SIMD4 kernel | Speedup |
|---:|---:|---:|---:|---:|---:|
| 4 | 5120 | 5120 | 126.041 us | 124.583 us | 1.0117x |
| 4 | 5120 | 17408 | 93.541 us | 93.125 us | 1.0045x |
| 4 | 17408 | 5120 | 96.458 us | 96.042 us | 1.0043x |

The absolute ordering between shapes reflects occupancy as well as bytes read;
the relevant comparison is paired baseline versus candidate for each shape.

## Disposition

Closed as a performance loss relative to the integration gate. It is exact but
does not approach the required `1.5x` kernel speedup or a credible 5 ms target
pass saving. The original templated kernel is already inlined and unrolled, so
the compiler can eliminate the apparent repeated Q4 loads in the scalar source
loop. Explicit `float4` accumulator organization produces effectively the same
device work. Keep the path default off and do not spend an AOT cycle on it.

A materially different result requires a different activation/weight mapping,
not source-level vector spelling: for example verifier-specific interleaved Q8
activation storage consumed directly by a joint-row kernel, or a new DPAS pack
whose M=4 mapping clears correctness and the production comparator gate.
