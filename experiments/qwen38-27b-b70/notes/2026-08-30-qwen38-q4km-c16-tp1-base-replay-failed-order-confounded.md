# Qwen3.8-27B Q4_K_M c16 TP1 deep-base replay: failed, order-confounded

The deep-base replay matched 11/16 frozen token-ID sequences despite all configurable integration optimization doors being disabled. Completion, cache, isolation, collision, WDC-negative, kernel, and cleanup gates passed; 12.769373376871481 tok/s is diagnostic only.

This does **not** yet prove a base-kernel race. Post-run audit found the pilot and replay had different prompt request-start orders. The client barrier synchronized release but did not stabilize prompt-to-slot assignment within the cohort. Because batch-row placement can change floating-point trajectories, request order is a remaining confounder.

The harness now supports an indexed launch stagger. The next pilot uses 10 ms per prompt index (150 ms total for c16) inside the unchanged 750 ms server admission window. This keeps all requests in one concurrent cohort while deterministically ordering their arrival.
