# Ornith 1.5 35B-A3B: direct oneMKL router GEMV changes generation

Date: 2026-08-23 EDT

Status: **CLOSED CORRECTNESS NEGATIVE — do not time or ship**

The accepted-stack serialized profile identified the 40 per-layer router
projections as a meaningful remaining dense boundary. Each decode call is an
FP32 `[256,2048]` weight multiplied by one `[2048,1]` activation, but the stock
SYCL backend sends it through oneMKL's general GEMM entry point. Because Ornith
is Qwen-derived, replacing this exact one-column call with GEMV was screened as
a narrow transfer candidate.

The default-off door required FP32 source/input/output, the exact `2048→256`
one-column shape, contiguous buffers, an unsplit weight, the complete row
range, and a destination named `ffn_moe_logits-*`. Instrumentation reported
5,080 hits in the forced 128-token candidate, proving that all intended router
calls took the candidate path.

It failed before timing. In the same frozen candidate binary, the door-off run
matched the canonical transcript SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`,
while the door-on output was
`8036dc4c82762b8e87c7f91d07b7766c117124e4cb0be6144badeee4d805c224`.
The generated text first differed at byte 456. GEMV therefore changed FP32
reduction behavior enough to alter downstream routing or sampling. No
performance, server, or canary result is reported.

The complete candidate source is preserved at
`../patches/llamacpp-ornith15-router-gemv-correctness-negative-20260823.patch`.
The accepted source and binary were restored; this is not part of the user
package.
