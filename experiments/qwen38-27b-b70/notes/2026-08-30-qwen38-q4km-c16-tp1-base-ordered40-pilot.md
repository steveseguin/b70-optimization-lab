# Qwen3.8-27B Q4_K_M c16 TP1 ordered-40 deep-base pilot

The 40 ms indexed-stagger pilot passed both request-order gates and all model/system gates.

- Client start order: exactly `c000` through `c015`; first-to-last span 581.94 ms.
- Server task order: exactly `1` through `16`, assigned in one cohort.
- Outputs: 16/16 complete 128-token sequences; zero cached tokens; complete isolation; zero collisions.
- Systems: WDC absent, empty kernel-error file, clean shutdown.
- Diagnostic-only aggregate rate: 12.779908775862932 tok/s.

The prior unordered deep-base oracle matched 12/16, confirming slot ordering changes trajectories. A new ordered40 oracle was frozen and a fresh replay preregistered. No performance result is promoted from this diagnostic lane.
