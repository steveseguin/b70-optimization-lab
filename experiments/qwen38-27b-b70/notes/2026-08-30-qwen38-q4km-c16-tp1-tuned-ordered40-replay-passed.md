# Qwen3.8-27B Q4_K_M c16 TP1 tuned ordered-40 replay: passed

The full tuned TP1 stack passed **16/16 exact token-ID sequences** on a fresh server when prompt-to-slot order was controlled.

- Client order: exactly `c000..c015`, 581.88 ms span.
- Server: one monotonic 16-request cohort.
- Outputs: all 128 tokens complete, zero cached tokens, complete isolation, zero collisions.
- Systems: WDC absent, empty kernel-error file, clean shutdown.
- Diagnostic aggregate rate: 15.499927587376385 tok/s.
- Result SHA-256: `7af7b8b1477972f57b9fe994ac5d4c0c739bfeeabbbc3a2cd788a3876e02cf5a`.

This corrects the earlier interpretation: the failed unordered replays did not prove tuned-kernel nondeterminism because prompt-to-slot mappings changed. Both deep-base and full-tuned TP1 profiles are exact under controlled order. The same protocol now moves to TP2.
