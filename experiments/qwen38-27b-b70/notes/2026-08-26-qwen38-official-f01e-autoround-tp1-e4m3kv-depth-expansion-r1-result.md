# Official f01e AutoRound TP1 E4M3-KV depth expansion R1

The authorized expansion passed all six exact nonzero depths and the complete quality battery on the same pinned current official image as the green sentinel: AutoRound TP1/MTP0, eager execution, FP8 E4M3 KV, `f01e24f6…` / `ac7509e2b`.

| Active context | decode tok/s | TTFT ms |
|---:|---:|---:|
| 2K | 12.106811568755516 | 1531.6096390015446 |
| 4K | 11.986857838637341 | 2804.6507950057276 |
| 8K | 12.085894881224178 | 5816.869347996544 |
| 16K | 12.178365844454287 | 12452.376738991006 |
| 24K | 12.15958526221534 | 19853.869445985765 |
| 32K | 12.157390534237836 | 27972.64591899875 |

Every request had its exact prompt depth, 128 returned token IDs, zero cached tokens, no truncation/context shift, and a valid 99-interval decode window. The full battery passed 7/7 exact cases, 8/8 deterministic repeats with one hash, the 8K needle, and 24/24 baseline comparisons. All 19 model files again passed coherent direct and ordinary verification.

This qualified curve replaces the current-image singleton publication, including its earlier 8K value of 11.824452787933243 tok/s. It does not erase the sentinel evidence, and the older immutable `e9d1398d9` output-divergence quarantine remains historical evidence for that runtime. `x=0` stays missing. No graph, TP, MTP, other-KV, headline, protected-speed, or automatic descendant authority transfers.

The terminal receipt is passed and terminal, cleanup is clean, the campaign container is absent, and port 19469 was closed at sealing. Compact evidence is in `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-e4m3kv-depth-expansion-r1-result.json`; raw receipts remain at `/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-e4m3kv-depth-expansion-20260826-r1`.
