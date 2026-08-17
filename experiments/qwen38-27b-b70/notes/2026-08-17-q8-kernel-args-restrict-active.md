# Qwen3.8 27B Q8 TP2 MMVQ kernel-argument no-alias contract

Date: 2026-08-17

Status: active; claimed by the ASRock two-B70 host.

## Hypothesis

The accepted reordered-Q8 kernels pass distinct weight, activation, and output
allocations, but that no-alias relationship is not visible at the SYCL kernel
entry. Intel documents `[[intel::kernel_args_restrict]]` as an unchecked
kernel-level no-alias promise that can enable more aggressive memory scheduling.
The hot Q8 kernel is bandwidth-bound and its inner helpers already use
`__restrict__`, so exposing the same fact at the generated kernel boundary may
remove conservative dependencies without changing loads, arithmetic, launch
geometry, or output values.

This is materially different from the closed operand preload, weight prefetch,
cache-hint, fixed-shape, GRF, and DP4A experiments: it changes only compiler
alias information at the kernel boundary.

## Contract

- derive an isolated treatment source/build from the checksum-gated accepted
  DP4A2 x SG24 Q8 stack;
- apply the attribute only to the live reordered-Q8 standalone, multi-column,
  fused pair, fused attention triple, and processed recurrent quad launches;
- first verify that IntelLLVM 2026.1.1 accepts the GPU attribute and inspect
  BMG-G31 AOT metadata/disassembly for real code-generation movement;
- keep the accepted binary as the control; do not add a second in-binary
  specialization because that previously perturbed control IGC code generation;
- require a bounded TP2 smoke with the full fusion census and zero verifier
  mismatches, then an accepted-treatment-accepted fresh-process bracket;
- run endpoint and quality gates only for a repeatable positive result outside
  measurement noise;
- stop immediately on a SYCL exception, device loss/reset/hang, or any output
  mismatch.

No model, quantization, tensor split, FP32 accumulation order, KV type,
sampling, or speculative mechanism changes in this experiment.
