# Qwen3.8-27B Q4_K_M c16 TP2 tuned ordered-40 replay: passed

The full tuned TP2 stack passed **16/16 exact token-ID sequences** on a fresh server under controlled prompt-to-slot order.

- Client order: exactly `c000..c015` within the 750 ms admission window.
- Server: one monotonic 16-request cohort.
- Outputs: all 128 tokens complete, zero cached tokens, complete token-ID isolation, zero collisions.
- Systems: WDC absent, empty kernel-error file, clean shutdown.
- Diagnostic aggregate rate: 17.59699274578496 tok/s.
- Result SHA-256: `b9982962085a8fc7318ec1ed66a86e29de6e822075e20856b3928888045836cc`.

Together with the tuned TP1 16/16 pass, this clears both local one- and two-B70 tuned c16 lanes. The earlier 9/16 failures were comparisons across changing prompt-to-slot mappings, not valid evidence of a tuned-kernel race. Deep-base and full-tuned TP1 both reproduced 16/16 once request order was controlled, and tuned TP2 did the same.

These fully synchronized c16 rates remain diagnostic rather than promoted throughput results. The next scaling step must preserve deterministic prompt order at higher concurrency; c64 requires either a longer admission window than the current 1000 ms source limit or a stronger ordered-submit mechanism. WDC remains unqualified until it passes diverse realistic output identity and the corrected ordered concurrency gate.

Evidence: `/mnt/fast-ai/bench-results/qwen38-q4km-c16-tp2-tuned-ordered40-replay-20260830-r1-concurrency-control-attempt1/`
