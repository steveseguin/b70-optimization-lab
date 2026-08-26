# TP2/MTP4 eager F16 exact-4K sentinel — Grade C result

The preregistered current-f01e AutoRound TP2/MTP4 exact-4K sentinel passed every local gate. The conventional 99-interval decode result is **21.080466832575162 tok/s**, TTFT is **4336.120582011063 ms**, and the isolated native-MTP counters are **90 accepted / 148 drafted**.

The request used exactly 4,096 active prompt tokens, returned 128 tokens, and reported zero cached prompt tokens. Its output-token SHA-256 is `3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0`, exactly matching the frozen same-image, same-topology TP2/MTP0 eager/F16 target.

The full quality and same-topology baseline battery passed: seven exact cases, eight deterministic repeats with one hash, the long-context needle, 24 baseline comparisons, and cache zero on all 16 requests. Both TP2 ranks, direct model verification, rank-cache isolation, container cleanup, and port cleanup also passed.

Explicit human per-cell adjudication promotes only exact 4K to Grade C measured evidence. The raw arm correctly grants no automatic publication or expansion authority. Exact 8K remains the existing speedless token-99 target-divergence quarantine, and x0/2K/16K/24K/32K remain missing. No other topology, MTP depth, graph mode, KV type, headline, record, or protected result changes.

Raw root: `/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-20260826-r1`

Compact result: `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-r1-result.json`
