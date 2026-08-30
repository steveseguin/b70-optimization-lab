# Qwen3.8-27B Q4_K_M TP2 single-cohort c64 replay: failed

The fresh replay failed at **54/64 exact token-ID sequences** even though all 64 requests launched in the same logged millisecond. This rules out HTTP admission timing as the root cause of the remaining nondeterminism.

- Pilot and replay used identical TP2 tensor `1,1`, Q4_K_M, MTP0, context 32768, batch 4096, ubatch 256, c64, and 750 ms admission settings.
- All responses completed with 128 retained tokens; all prompt-cache counts were zero and cross-base collisions were zero.
- WDC was disabled and absent; the kernel-error artifact is empty and server cleanup was clean.
- Replay diagnostic aggregate rate: 55.277603827564064 tok/s. It is not publishable.
- The ten mismatching prompts were `capacity-c006`, `benchmark-c011`, `capacity-c014`, `index-c017`, `capacity-c022`, `benchmark-c027`, `cache-c032`, `benchmark-c051`, `cache-c056`, and `capacity-c062`.

The 50 ms and 750 ms admission experiments are closed. The next bounded screen uses a shorter c16 shape on TP1 and TP2. If TP1 is exact and TP2 is not, the custom two-GPU collective/fusion path becomes the primary suspect; if both fail, the investigation moves to shared single-GPU kernels.

Result SHA-256: `9736d63f71d64332fe88270e1d8e81874647393526a5631de554e76e689de51e`.

Evidence: `/mnt/fast-ai/bench-results/qwen38-q4km-tp2-queue-settle750-c64-replay-20260830-r1-concurrency-control-attempt1/`
