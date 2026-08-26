# Qwen3.8 AutoRound TP1 eager and PIECEWISE exact-depth R3

R3 passed both preregistered TP1/MTP0/F16 arms on the pinned official `f01e24f6…` image: six exact nonzero active-context depths in eager mode and the same six in PIECEWISE mode. Every depth request returned exactly 128 token IDs with the exact prompt count, zero cached tokens, no truncation/context shift, and a valid 99-interval decode window. Both servers also passed the full text-quality battery: 7/7 exact cases, 8/8 deterministic repeats with one hash, the 8K needle, and 24/24 baseline comparisons.

| Active context | eager decode tok/s | eager TTFT ms | PIECEWISE decode tok/s | PIECEWISE TTFT ms |
|---:|---:|---:|---:|---:|
| 2K | 11.919327130453762 | 1520.064229000127 | 30.075429359128265 | 1363.4014569979627 |
| 4K | 12.115385179434695 | 2758.202084005461 | 29.41347238250489 | 2474.7674179961905 |
| 8K | 11.919958636516224 | 5644.954247007263 | 29.01975248295894 | 5060.748901989427 |
| 16K | 12.112539400630334 | 11681.28542600607 | 28.192761390148664 | 10545.48624700692 |
| 24K | 12.039525807023459 | 18096.79437900195 | 27.463520678399885 | 16543.705064992537 |
| 32K | 12.1065485687806 | 24927.870916988468 | 26.759466347975422 | 22671.85614600021 |

These are additive, profile-specific Grade C context-shape measurements. They do not replace the separately protected short-decode anchors or the existing FULL_AND_PIECEWISE context curve. In particular, PIECEWISE is nearly tied with the older full+piecewise curve at 2K, but is not the same runtime/source profile and cannot overwrite it. `x=0` remains missing because no zero-context request was measured. No estimate, interpolation, headline replacement, or LocalMaxxing submission is authorized.

R1 and R2 remain transparent harness closeouts. R1 stopped before a container or GPU service launched when a live-origin mismatch did not propagate out of command substitution. R2 successfully started and quality-qualified both servers, but all depth helpers failed before requests because the launcher omitted `--context-capacity`. R3 used fresh roots and added only `--context-capacity 32896`.

The terminal receipt is passed and terminal, both campaign containers are absent, and ports 19466/19467 were closed at sealing. The compact result is `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-r3-result.json`; raw receipts remain at `/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-20260826-r3`.
