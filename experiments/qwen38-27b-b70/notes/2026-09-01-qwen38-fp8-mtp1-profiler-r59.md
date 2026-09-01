# Qwen3.8 FP8 TP2 MTP1 bounded profiler R59

Date: 2026-09-01

R59 profiled the accepted graph-off R50 MTP1 stack for a bounded decode window
after one unrepeated natural prompt (44 input tokens, 96 returned tokens,
`cached_tokens=0`). Profiling was limited to five active iterations after ten
delayed iterations. Its timings are instrumented and **must not** be used as a
throughput claim.

| Device-kernel category | Rank 0 | Rank 1 |
| --- | ---: | ---: |
| oneCCL all-reduce | `51.09%` | `50.32%` |
| GEMM | `44.57%` | `45.31%` |
| combined | **`95.66%`** | **`95.63%`** |
| GDN recurrent-spec kernel | `0.56%` | `0.58%` |
| GDN convolution-spec kernel | `0.40%` | `0.41%` |

Each rank recorded 1,056 all-reduce kernels and 2,488 GEMM kernels in the
bounded trace. Absolute durations include profiler overhead, but the symmetric
rank-level proportions make the next bottleneck unambiguous: further work
should overlap or fuse TP communication with block-FP8 GEMM, not spend the next
arm tuning the already-small GDN kernels.

This also explains why simply enabling the existing AsyncTP machinery is not a
valid next knob. The earlier PR #52683 integration reached the compiler but
produced zero replacements: its XPU primitive covers static W8A8, while this
official checkpoint uses per-token group-128 activation quantization and
block-scaled weights. A real implementation must communicate the paired
activation scales and preserve exact target output; the prior result is
documented in
[the R14/R15 note](2026-08-26-qwen38-fp8-tp2-asynctp-pr52683-r14-r15-result.md).

The launcher now accepts a default-off `PROFILER_CONFIG` only when paired with
`PROFILER_DIR`. Ordinary package launches are unchanged.
