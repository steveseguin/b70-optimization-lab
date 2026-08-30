# Qwen3.8 Flash-Next FP8 A16 late-prefill trace preregistration

Date: 2026-08-30
Status: frozen before GPU launch

## Question

A15 retained the short-output authority and the faster short rate, but its two
exact-4K rows diverged at generated token 2. Fixed-input tests subsequently
showed bit-identical QSA score/select/attention, local FP8 MoE, and TP4 XCCL
reduction paths. A16 asks where the values first differ inside one full late
prefill invocation.

## Frozen arm

A16 is the A15 TP4/EP4/eager/MTP0, 4,352-token, PLE-only placement with exactly
two changes:

1. vLLM head `9f720cd4aa6c8a8b045f54dfa10f5b8611caccbd` adds an opt-in,
   report-only trace;
2. rank 0 records one invocation whose maximum logical position is at least
   4,000.

The trace hashes the exact raw bytes of model positions, model input, all three
delayed-hyperconnection outputs after every decoder layer, and final model
outputs. It writes once with exclusive creation. It does not alter weights,
arithmetic, placement, graph mode, scheduler settings, cache capacity, request
payloads, or any performance selector. Tensor transfers will perturb timing,
so A16 receives no speed credit.

The unchanged full A15 client battery is retained to reach the established 4K
request without inventing a new payload. If an existing authority assertion
fails after the trace is captured, preserve that result; the diagnostic is not
allowed to weaken the gate. A fresh A17 trace is required before interpreting
the first differing boundary.

Frozen artifacts:

- vLLM patch `0020-Add-opt-in-Qwen4Exp-repeatability-trace.patch`, SHA-256
  `b055f6165c7af6b30ecc3b7134c86816cdc0f82493f41e1f9c15899e2f501315`;
- launcher wrapper `0b5482ab292bf8f054fab026ad9a3c9eef9ef4a7522c17a74a16677b317f7f2b`,
  generated source `d39133ae6d2e7a3ff186c6765877b3dfd55f69573a3c2e1363a60c9249f5d7f2`;
- client wrapper `171816212130fdc0453bf27f576015c88575c45ff87da8543f6cbe0608a6a4ac`,
  generated source `8a361379a8533722ca37dccaba64581605125d3603a7855c0ffac63505223f3e`;
- supervisor wrapper `a4d93efb63511c5a7340b45b522b2f07b675b45d40c455601deae79768f5cffc`,
  generated source `dea6b0c18dee0910797157dd09465ff61da11e394612302c00be65325f8d5494`.

No protected result is changed by this arm.
