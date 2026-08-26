# TP4/MTP1 PIECEWISE exact-4K sentinel R1 result

The preregistered current-f01e TP4 native-MTP1 PIECEWISE/F16 exact-4K sentinel passed. The conventional 99-interval decode rate was `18.823672180898463 tok/s`, TTFT was `2349.6064160135575 ms`, and the isolated request accepted `56/71` drafted tokens. All 128 output token IDs matched both same-image TP4/MTP0 targets (eager and PIECEWISE) and the preregistered TP4/MTP1 eager mechanism parent; their shared hash is `3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0`.

The exact/cache-zero gate, complete objective and baseline quality battery, PIECEWISE graph capture identity, four-worker TP topology, four per-rank cache namespaces, model verification, and cleanup all passed. The launch was bound to Git head `936acde5708fe0ad32775c3adc72fc926e97f77c`.

This is evidence only. It grants no family/site publication authority, changes zero site cells, authorizes no descendant run, and does not replace protected or historical values. Only exact 4K is supported; x0, 2K, 8K, 16K, 24K, and 32K remain missing for this profile. In particular, this pass does not clear the existing current-f01e PIECEWISE 8K token-99 corruption signature (`411` versus eager target `579`).

Raw root: `/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp4-mtp1-f16-piecewise-4k-sentinel-20260826-r1`
