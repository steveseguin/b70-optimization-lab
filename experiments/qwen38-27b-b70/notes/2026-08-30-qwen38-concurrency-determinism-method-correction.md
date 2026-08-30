# Qwen3.8 concurrency determinism method correction

The prior concurrency oracle method synchronized thread release but did not preserve prompt-to-slot assignment. On this backend, batch-row placement changes numerical trajectories even when every request belongs to the same nominal cohort. Exact-output comparisons across different prompt/slot mappings are therefore invalid.

Corrected method:

1. Disable prompt caching and retain complete token IDs.
2. Give every prompt a stable index and request ID.
3. Release all client workers from one barrier, then delay request `i` by `i * launch_stagger_ms`.
4. Use a server admission window longer than the total indexed stagger so every request still enters one concurrent cohort.
5. Verify client `request_started_epoch_s` sorts exactly by prompt index and server task assignment is monotonic.
6. Freeze a shape/topology/profile-specific token-ID oracle only after order, completion, cache, isolation, collision, WDC, kernel, and cleanup gates pass.
7. Require a fresh server to reproduce every frozen token-ID sequence.

At c16, a 10 ms stagger was insufficient (`0,2,1,...`); 40 ms produced stable `0..15` order in a 581–582 ms span inside a 750 ms admission window. Under that control, both tuned TP1 and tuned TP2 replayed 16/16 exactly. Never infer a kernel race from an unordered concurrent replay again.
