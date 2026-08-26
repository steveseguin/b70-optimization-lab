# Official f01e AutoRound TP1 E4M3-KV 8K sentinel R1 result

The preregistered one-dose sentinel passed. On the pinned official `f01e24f6…` image (`ac7509e2b`, vLLM `0.27.2rc1.dev77`), the AutoRound TP1/MTP0 eager server booted with `fp8_e4m3` KV and its one exact 8K request measured **11.824452787933243 decode tok/s** with **5965.314737986773 ms TTFT**. The request had exactly 8,192 prompt tokens, 128 returned token IDs, zero cached tokens, and every exact-depth gate passed.

The complete quality battery also passed: 7/7 exact cases, 8/8 deterministic repeats with one hash, the 8K needle, 24/24 baseline comparisons, and cache zero. Model verification passed for all 19 files through coherent direct and ordinary reads. The terminal receipt is passed and terminal, the campaign container is absent, and port 19468 was closed at sealing.

This result supersedes the old `e9d1398d9` output-divergence closure only for this exact current-runtime TP1/MTP0/eager/fp8_e4m3/8K cell. The older 24.1009 tok/s, 3/20-stable-match observation remains valid historical evidence for its immutable e9d runtime. No other depth, graph mode, TP, MTP, or KV cell is inferred; descendant expansion remains a separate preregistered decision. `x=0` remains missing, and all protected F16 and headline values remain untouched.

Compact evidence is in `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-e4m3kv-8k-sentinel-r1-result.json`; raw receipts remain at `/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-e4m3kv-8k-sentinel-20260826-r1`.
