# Qwen3.8-27B Q4_K_M c16 TP1 reference/no-dedup pilot

The targeted no-dedup pilot passed all oracle-generation gates at a diagnostic 15.80102261204573 tok/s. The live census confirmed `GGML_SYCL_Q8_QUANT_DEDUP=0`; 16/16 responses completed, cache counts were zero, token-ID isolation was complete, collisions were zero, WDC was absent, the kernel-error file was empty, and cleanup was clean.

It matched 14/16 sequences from the prior intermediate-reference pilot, showing that disabling dedup changed two trajectories. This is not evidence of improved determinism by itself. A topology/profile-specific no-dedup oracle was frozen and a fresh 16/16 replay preregistered.
