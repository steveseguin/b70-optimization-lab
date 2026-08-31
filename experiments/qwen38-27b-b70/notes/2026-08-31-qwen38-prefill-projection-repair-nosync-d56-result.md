# Qwen3.8 no-barrier projection repair D56 result

D56 passed: explicit device-wide barriers are unnecessary around the M=512
padded projection repair.

- Four fresh processes produced the same complete 64-layer trace byte for byte
  (`30826f20...3934`).
- Every decoder input/output/residual and complete token stream matched.
- The only treatment removed from D53 was `torch.xpu.synchronize()`; padding,
  projection roles, slicing, image, prompt, and runtime flags were unchanged.

This establishes ordinary XPU stream dependencies as sufficient for the
repair's copy/GEMM/slice ordering. D57 now runs the non-instrumented 12-prompt
strict suite with barriers disabled, compares all token IDs to D54, and measures
the full-suite TTFT distribution. D56 itself is not a performance result.
