# TP1/MTP0 E4M3 FULL_AND_PIECEWISE exact-4K sentinel result

This cell is a **structural quarantine**, not a measured speed result. The current pinned f01e/ac7509e2 image successfully booted the AutoRound artifact with TP1, MTP0, `fp8_e4m3` KV, and `FULL_AND_PIECEWISE` graph mode. It captured PIECEWISE sizes 1 and 2 plus the size-1 FULL decode graph. Exact 4K depth, all helper gates, 16/16 cache-zero requests, TP1/cache isolation, all 19 direct-and-ordinary model checks, the full quality battery, and cleanup passed.

The candidate's 128 token IDs did not match either frozen same-image E4M3 parent. The eager and PIECEWISE parents agree at SHA `a3d7ad63…`; the candidate produced `3febb16e…`, first differing at token 95 (one-based: candidate 248046, target 220). That is terminal rc38 `quarantined-target-parity-failed` under the preregistered interpretation.

The observed timing remains diagnostic evidence only. It must not populate a site speed, headline, record, or descendant cell. Only the exact TP1/MTP0/FULL_AND_PIECEWISE/E4M3/4K cell may be classified as quarantined; every other depth, topology, MTP depth, graph mode, and KV dtype remains unchanged.

Compact evidence is in `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp0-e4m3kv-full-and-piecewise-4k-sentinel-r1-result.json`; raw evidence remains at `/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-mtp0-e4m3kv-full-and-piecewise-4k-sentinel-20260826-r1`.
