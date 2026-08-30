# Qwen3.8-27B Q4_K_M c16 TP1 tuned ordered-40 pilot

The full tuned TP1 pilot passed order, isolation, and systems gates at a diagnostic 15.502510071178278 tok/s.

- Client request order: exactly `c000..c015`, 581.61 ms span.
- Server: one monotonic cohort.
- Output: 16/16 complete 128-token sequences, zero cached tokens, complete isolation, zero collisions.
- Systems: WDC absent, empty kernel-error file, clean shutdown.

Its 9/16 match to the earlier unordered tuned oracle is a known prompt-to-slot order boundary, not a determinism failure. A tuned ordered40 oracle was frozen and a fresh 16/16 replay preregistered.
