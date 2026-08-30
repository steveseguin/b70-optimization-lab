# Qwen3.8-27B Q4_K_M c16 TP1 reference pilot

The first reference-profile pilot passed its oracle-generation gates at a diagnostic 15.737134018788652 tok/s. It completed 16/16 responses with zero cached tokens, complete token-ID isolation, zero collisions, WDC absent, an empty kernel-error file, and clean shutdown.

Live door census showed this is an intermediate—not fully upstream-like—reference profile. Explicit lab fused attention/GDN/MMVQ/Q8 handoff and forced reorder doors were off, but integration defaults for general optimization/DNN/fusion/MMQ, Q8 quantization dedup, MMVQ pad/split, and MKL direct remained on. The 16-row intermediate oracle was frozen and a fresh replay preregistered before drawing any conclusion.
