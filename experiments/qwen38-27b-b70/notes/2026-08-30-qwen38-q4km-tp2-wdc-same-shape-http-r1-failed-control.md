# Qwen3.8-27B Q4_K_M TP2 WDC same-shape HTTP r1: failed control

The campaign stopped at its first control gate. No WDC candidate ran and no speed claim is valid from this campaign.

- Configuration: TP2 tensor `1,1`, Q4_K_M, MTP0, reorder enabled, WDC disabled, 64 concurrent HTTP requests, 128 retained tokens per request.
- Fresh control replay: **54/64** token-ID sequences exactly matched the frozen c64-shaped control oracle.
- Diagnostic aggregate throughput: **160.651068 tok/s**. This number is not publishable because the exact-output gate failed.
- All requests completed, prompt-cache counts were zero, and no kernel fault was recorded.
- The ten mismatches were coherent but diverged mostly around generated token 11 through 25 (one at token 127), consistent with run-to-run request scheduling or batch-composition sensitivity.

This disproves the idea that merely comparing the candidate at the same nominal c64 shape is sufficient. The next experiment adds a default-off, explicit burst-admission settle window and requires two fresh 64/64 control replays before any WDC candidate is allowed to run.

Evidence: `/mnt/fast-ai/bench-results/qwen38-q4km-tp2-wdc-same-shape-http-20260830-r1-concurrency-control-attempt1/`
