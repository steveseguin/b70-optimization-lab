# Qwen3.8 FP8 TP2 c64 P2P1 profiler R11 result

Date: 2026-08-26. Status: **diagnostic only; not a performance or promotion result**.

R11 captured eight profiled engine iterations from the qualified FP8 TP2 c64
shape. The capture completed and cleaned up normally, but the outer runner's
final qualifier failed because it invoked pilot mode without `--oracle-out`
and the preregistration incorrectly required exact sequential-oracle identity
at c64. Batch-shape output variation is already an accepted property of this
lane. The harness itself classified the output
`output-isolation-qualified-shape-variant`: all 64 requests returned their full
128-token completions, all complete token-ID identities were present, all
cache counts were zero, and there were no cross-base oracle collisions. Only
5/64 sequences matched the sequential oracle exactly.

The profiled `430.992179 tok/s` is instrumentation-distorted and **must never
be used as model speed evidence**. The promoted unprofiled c64 result remains
`774.394144 tok/s`.

## Device-time attribution

The two rank traces agree on the dominant work. Percentages below use each
rank's total self XPU time; the average is descriptive, not an extrapolation.

| group | rank 0 | rank 1 | two-rank average |
| --- | ---: | ---: | ---: |
| GEMM kernels | 414.966 ms (57.87%) | 423.161 ms (59.87%) | 419.063 ms (58.86%) |
| named GDN kernels | 181.377 ms (25.29%) | 182.236 ms (25.78%) | 181.806 ms (25.54%) |
| all-reduce | 74.754 ms (10.43%) | 55.163 ms (7.80%) | 64.959 ms (9.12%) |
| all-gather | 3.420 ms (0.48%) | 3.531 ms (0.50%) | 3.476 ms (0.49%) |
| other device work | 42.537 ms (5.93%) | 42.764 ms (6.05%) | 42.651 ms (5.99%) |
| total self XPU | 717.054 ms | 706.855 ms | 711.955 ms |

There were 2,048 `_xpu_C::fp8_gemm` calls per rank over eight iterations, or
256 calls per profiled decode iteration. There were 1,032 all-reduces per rank,
or 129 per iteration.

The promoted c64 lane needs an 11.50% reduction in wall time to reach
875 tok/s. Because all-reduce accounts for only about 9.1% of profiled device
time, even the impossible case of eliminating it entirely would not reach the
target by itself. The next work should target GEMM first and GDN second while
preserving the existing direct-P2P setting.

## FP8 scratchpad hypothesis

The current oneDNN FP8 W8A8 implementation allocates a fresh scratchpad tensor
inside every GEMM call. The rank-0 CPU table also reports 3,300
`aten::empty_strided` calls and 112.984 ms of self CPU time over the eight
profiled iterations. This correlation is a **hypothesis**, not causal proof:
profiler overhead prevents translating it into an unprofiled speedup.

The next bounded candidate is therefore a clean-build FP8 scratchpad cache,
modeled after the existing INT8 cache. It must be tested first with varied
inputs and repeated direct/graph execution to rule out asynchronous scratchpad
aliasing, then against the frozen c64 endpoint harness. Nothing from this R11
capture authorizes a package or website update.

## Evidence

- [Harness summary](../data/qwen38-fp8-tp2-http-p64-p2p1-profiler-20260826-r11/harness-summary.txt)
- [Rank 0 profiler table](../data/qwen38-fp8-tp2-http-p64-p2p1-profiler-20260826-r11/profiles/profiler_out_0.txt)
- [Rank 1 profiler table](../data/qwen38-fp8-tp2-http-p64-p2p1-profiler-20260826-r11/profiles/profiler_out_1.txt)
- [Raw result](../data/qwen38-fp8-tp2-http-p64-p2p1-profiler-20260826-r11/result.json)
- [Frozen preregistration](../data/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-profiler-r11-prereg.json)
- [Runner](../scripts/run-qwen38-fp8-tp2-http-p64-p2p1-profiler-r11.sh)

The compressed rank traces, runtime identity, server command, direct model
verification, and cleanup receipt are preserved in the same evidence directory.
