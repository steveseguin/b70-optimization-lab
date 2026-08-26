# Current f01e AutoRound TP2 PIECEWISE/F16 MTP2 exact-4K sentinel R1

The preregistered two-card native-MTP2 PIECEWISE/F16 sentinel passed. On the
pinned official `f01e24f6…` image (`ac7509e2b`, vLLM `0.27.2rc1.dev77`), the
TP2 server measured **18.40866489344403 conventional decode tok/s** at exact
4K, with **3125.5207280046307 ms TTFT**. The distinct historical 100-event
diagnostic was 18.59461100347882 tok/s; it is not the publication metric.

The isolated exact request drafted 94 tokens and accepted 80
(`0.851063829787234`). Every exact-depth gate passed with 4,096 prompt tokens,
128 returned token IDs, and zero cached tokens. The candidate exactly matched
both pinned same-image parents—the TP2/MTP0 PIECEWISE/F16 target and the
TP2/MTP2 eager/F16 mechanism parent—across all 128 tokens (hash `3febb16e…`).

The full objective and eager-MTP2 baseline battery passed: 7/7 exact cases,
deterministic 8/8 repeats with one hash, the long-context needle, 24/24
baseline comparisons, and cache zero on all 16 quality requests. PIECEWISE
size-one capture, both TP2 worker ranks, isolated `rank_0_0` and `rank_1_0`
caches, all 19 model files, and the terminal cleanup receipt also passed. The
compact result binds every file in the raw root by relative path and SHA-256.

This packet records exactly one Grade C candidate cell pending a separate
human publication decision: current `f01e/ac7509e2`, AutoRound INT4,
TP2/MTP2/PIECEWISE/F16, exact 4K. It does not edit the family contract or
website. `x=0`, 2K, 8K, 16K, 24K, and 32K remain missing for this tuple. The
quality-only 8K needle is not an exact-8K performance cell. No other graph
mode, TP, MTP dose, KV mode, image, headline, submission, descendant, or
historical/protected result is authorized or replaced.

Compact evidence is in
`experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp2-f16-piecewise-4k-sentinel-r1-result.json`;
raw receipts remain at
`/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp2-f16-piecewise-4k-sentinel-20260826-r1`.
