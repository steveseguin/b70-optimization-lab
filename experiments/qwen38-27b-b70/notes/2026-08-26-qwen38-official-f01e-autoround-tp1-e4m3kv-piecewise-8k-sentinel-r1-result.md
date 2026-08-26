# Official f01e AutoRound TP1 E4M3-KV PIECEWISE 8K sentinel R1 result

The preregistered one-dose PIECEWISE sentinel passed. On the pinned official `f01e24f6…` image (`ac7509e2b`, vLLM `0.27.2rc1.dev77`), the AutoRound TP1/MTP0 server used E4M3 KV and PIECEWISE graph capture size 1. Its exact 8K request measured **28.726353926869724 decode tok/s** with **5.397674360006931 s TTFT**. The request had exactly 8,192 prompt tokens, 128 returned token IDs, zero cached tokens, and every exact-depth gate passed.

The complete quality battery also passed: 7/7 exact cases, 8/8 deterministic repeats with one hash, the 8K needle, 24/24 baseline comparisons, and cache zero on every quality request. Model verification passed for all 19 files through coherent direct and ordinary reads. The terminal receipt is passed and terminal, the runner reports clean cleanup, and the campaign container and port 19471 were absent at terminal classification.

This is additive, profile-specific diagnostic evidence only for current `f01e/ac7509e2` TP1/MTP0/PIECEWISE/E4M3-KV at exact 8K. It does not replace a historical E4M3 value, a protected F16 or PIECEWISE route, or a headline result. It authorizes only the separately preregistered graph-depth expansion; expansion is not automatic, no descendant was executed by this result, and no other depth, TP, MTP, graph, KV, or `x=0` cell is inferred.

The sentinel is deliberately not published into `families/qwen-27b.json` or the generated site yet. Compact evidence is in `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-8k-sentinel-r1-result.json`; raw receipts remain at `/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-8k-sentinel-20260826-r1`.
