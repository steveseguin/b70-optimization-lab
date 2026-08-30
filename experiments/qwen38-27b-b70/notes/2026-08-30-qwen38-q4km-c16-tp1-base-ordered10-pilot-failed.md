# Qwen3.8-27B Q4_K_M c16 TP1 ordered-10 ms pilot: failed ordering gate

The model-output isolation gates passed, but the explicit request-order gate failed: observed start order began `0, 2, 1, 3, ...` rather than `0, 1, 2, 3, ...`. A 10 ms thread stagger was not large enough to dominate Python/HTTP scheduling jitter.

The diagnostic 12.790017114578324 tok/s rate is not publishable, and no ordered oracle was frozen. The next preregistered pilot uses a 40 ms per-index stagger (600 ms total for c16), still within the unchanged 750 ms server admission window.

Evidence: `/mnt/fast-ai/bench-results/qwen38-q4km-c16-tp1-base-ordered-pilot-20260830-r1-concurrency-control-attempt1/`
