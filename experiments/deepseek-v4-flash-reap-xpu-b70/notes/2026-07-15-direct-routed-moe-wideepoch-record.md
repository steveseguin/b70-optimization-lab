# DeepSeek V4 K160 direct routed-MoE and wide-epoch record

Date: 2026-07-15

## Result

The trustworthy nonspeculative TP4+EP4 record is now **43.766673 tok/s**
median for generated tokens 1-100 after TTFT. Three independent follow-up
suites measured 43.698550, 43.694210, and 43.667908 tok/s. All 48 strict rows
passed the fixed fresh-response gate with `cached_tokens=0`.

This is 4.87% above the preceding 41.733256 tok/s record. A same-build,
same-router-normalization control with only the direct routed-MoE path disabled
measured 41.991191 and 42.155092 tok/s. The direct fusion therefore adds
3.66-4.23% and removes approximately 0.84-0.97 ms from every decoded token.
LocalMaxxing approved the record as `cmrmnp7h81nntmj01lfenydgj`.

Evidence:

- candidate: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-direct-moe-wideepoch-candidate-20260715T2220Z`;
- direct-off control: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-router-norm-direct-off-control-20260715T2155Z`;
- vLLM: `a681dbb2b4b19c2c5a964817095b5f8c1f27ff48`;
- XPU kernels: `6522849b02894273b1e779b3c115527b5cdf3756`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`;
- selected `libccl.so.1.0` SHA-256:
  `53de2b6d65265803d64773546c1166ceed4ae43737f0fded776f5847b4b461c9`.

## Fusion boundary

The M=1 route now retains selected expert IDs and raw routing weights in the
native Xe2 path, applies the checkpoint's existing normalization, and feeds
the routed MXFP4 projection through a direct gather path. It removes the
generic framework sequence that materialized and reread per-expert
intermediates before the six selected outputs were weighted. The projection
math, clamp-at-10 SwiGLU arithmetic, and target weights are unchanged. M>1
continues to use the generic path.

Four cards passed 40/40 changed graph epochs for the exact low-level boundary.
The source remains default-off outside this explicitly qualified K160 M=1
record recipe.

## Why earlier long runs failed

The first direct-on candidate produced correct output through 27 exact
captures and then corrupted capture 28. The same-build direct-off control
failed at capture 28 and, after another workload interval, capture 58. Because
the failure survived disabling the new fusion and changed its token content,
the direct kernel was not the cause.

The Arc oneCCL low-latency ring encoded collective readiness with only an
11-bit sequence value. A long-lived reusable graph eventually reused a value
while stale readiness data remained visible, allowing one collective to
consume an old wire epoch. The symptom was a deterministic one-response token
corruption followed by recovery, which short canaries and ordinary two-suite
qualification could miss.

The repair gives collectives a 24-bit epoch plus a 7-bit communicator tag while
leaving point-to-point tag behavior unchanged. This expands the unique
collective readiness space by 8192x without another kernel, barrier, copy, or
host synchronization. All four live workers were verified to map the repaired
library.

## Sustained qualification

The repaired candidate passed 70/70 ordered exact captures with one unique
expected output, explicitly crossing both former failure positions 28 and 58.
It then passed four strict cold suites. This is important beyond this fusion:
long-lived graph replay can now be qualified without an 11-bit collective
epoch rollover silently invalidating otherwise exact kernels.

## Decision and next boundary

Promote both the direct M=1 routed-MoE fusion and widened collective epoch as a
single reproducible runtime identity. Continue nonspeculative optimization at
the routed GEMM2 epilogue/direct-gather boundary or next-weight prefetch, but
require an exact real-shape hardware gate projecting at least 0.50 ms/token
before another four-GPU server load. The 100/200 tok/s objectives remain open;
this result is the new trustworthy base, not the target.
