# Qwen3.8 projection-repair strict D55 replay result

D55 independently passed the complete strict qualification and matched D54.

- All 12 full token-ID sequences matched D54 by prompt ID.
- Cached tokens were zero, all objective canaries passed, and eight repeated
  greedy requests produced one output class.
- The class-balanced median was 24.801498 tok/s versus 24.804756 in D54.
- Shutdown and the bounded fault audit passed.

This qualifies the synchronized TP1/MTP0 implementation as a deterministic
correctness baseline. It is not the final optimized lane. D56 removes only the
explicit device-wide barriers while retaining padded arithmetic, then repeats
the four-process 64-layer trace before any strict speed comparison.
