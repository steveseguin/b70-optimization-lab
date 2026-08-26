# Qwen3.8 FP8 TP2 kernel profiler R26 result

Date: 2026-08-26. Status: **diagnostic complete; earlier comparison corrected**.

R26 completed cleanly on the pinned `1e90ffa672` kernel-only image. All 64
requests returned complete 128-token raw-ID outputs, cached-token counts were
zero, and there were no cross-base collisions. The profiler-distorted
`409.684178 tok/s` is not performance evidence and must not be published.

## The 5.99% “kernel regression” was a mismatched comparison

R23's single-c64 candidate result was compared to R10's c64 point after that
server had already run c1, c2, c4, c8, c16, and c32. The matching promoted-image
single-c64 R9 control is `730.598639 tok/s`; R23 is `728.035937`, only `-0.351%`.
R10's ladder-conditioned `774.394144` is `+5.994%` over R9—almost exactly the
apparent R23 loss. R17 and R25 are corrected on the same basis: `+0.752%` and
`-0.746%`, respectively. They remain below advancement gates, but they are not
4.9–6.4% regressions.

## Profile totals cannot be compared without composition normalization

The candidate trace captured five pure-decode and three chunk/mixed GDN
iterations. R11 captured seven decode and one chunk/mixed iteration. This is
proven by the 48-layer call counts: native/chunk calls were 240/144 in R26 and
336/48 in R11. The extra chunk iterations explain the larger generic GEMM and
total XPU time; treating those totals as a kernel-version delta would repeat
the same methodological error.

Matched operator tests remain the valid attribution evidence. Candidate deltas
were `+0.022%` and `+0.027%` for the two dominant FP8 MLP shapes and `+0.099%`
for pure-decode GDN b64. The newer wheel is therefore a no-win, not a measured
device-body regression.

The next experiment is a within-server conditioning factorial: c64 before,
then the c1→32 ladder, then repeated c64 after. This will establish whether the
6% effect is persistent runtime conditioning, measurement-order bias, or
ordinary run variance before any package or guide changes.

## Evidence

- [Structured result](../data/2026-08-26-qwen38-fp8-tp2-http-p64-kernel-profiler-r26-result.json)
- [Preregistration](../data/2026-08-26-qwen38-fp8-tp2-http-p64-kernel-profiler-r26-prereg.json)
- [Raw evidence and traces](../data/qwen38-fp8-tp2-http-p64-kernel-profiler-20260826-r26/)
- [Derived runner](../scripts/run-qwen38-fp8-tp2-http-p64-kernel-profiler-r26.sh)
- [Promoted R11 analysis](2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-profiler-r11-result.md)
