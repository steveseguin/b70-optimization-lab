# Current f01e AutoRound TP4 eager/F16 MTP1 8K sentinel R1

The preregistered four-card native-MTP1 sentinel passed. On the pinned official `f01e24f6…` image (`ac7509e2b`, vLLM `0.27.2rc1.dev77`), one TP4 eager server with F16 KV measured **13.709857016920843 conventional decode tok/s** at exact 8K, with **4.873025881999638 s TTFT**. The legacy 100-event definition was **13.848340421132164 tok/s**; it is retained separately and is not the site value.

The isolated exact request drafted 66 tokens and accepted 61 (`0.9242424242424242`). Every exact-depth gate passed with 8,192 prompt tokens, 128 returned token IDs, and zero cached tokens. The candidate exactly matched the frozen same-image, same-topology TP4/MTP0 oracle (`34e792cc…`) across all 128 tokens. The full objective and same-topology baseline quality battery passed: 7/7 exact cases, deterministic 8/8 repeats with one hash, the long-context needle, 24/24 baseline comparisons, and explicit cache zero on all 16 requests. All four workers, graph-off rank-cache isolation, all 19 model files, and cleanup also passed.

This publishes one additive Grade C measured cell: current `f01e/ac7509e2`, AutoRound INT4, TP4/MTP1/eager/F16, exact 8K. Other depths, MTP doses, graph modes, TP/KV choices, and `x=0` remain unmeasured. It does not replace the protected 71.900 graph route, the b2dd graph curve, the MTP0 oracle, any historical value, headline, or LocalMaxxing result. Expansion remains separately preregistered and never automatic.

Compact evidence is in `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-8k-sentinel-r1-result.json`; raw receipts remain at `/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-8k-sentinel-20260826-r1`.
