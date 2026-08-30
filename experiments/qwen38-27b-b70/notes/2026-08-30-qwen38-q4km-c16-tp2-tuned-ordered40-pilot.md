# Qwen3.8-27B Q4_K_M c16 TP2 tuned ordered-40 pilot

The tuned TP2 pilot passed order, isolation, and systems gates at a diagnostic 17.614204870176952 tok/s.

- Client order: exactly `c000..c015`, 573.61 ms span.
- Server: one monotonic 16-request cohort.
- Output: 16/16 complete 128-token sequences, zero cached tokens, complete isolation, zero collisions.
- Systems: WDC absent, empty kernel-error file, clean shutdown.

Its 7/16 match to the older unordered TP2 oracle is a known prompt-to-slot mapping boundary. A TP2 ordered40 oracle was frozen and a fresh exact replay preregistered.
