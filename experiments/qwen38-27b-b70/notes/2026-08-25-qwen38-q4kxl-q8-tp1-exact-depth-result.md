# Qwen3.8 UD-Q4_K_XL q8_0-KV TP1 exact-depth result

Date: 2026-08-25. State: **passed and ready for publication**.

The preregistered one-invocation curve completed with all seven exact cells,
five repetitions per point, a true `n_depth=0` row, exact `tg128` shape, and
clean teardown. The raw root is
`/mnt/fast-ai/bench-results/qwen38-q4kxl-q8-tp1-exact-depth-20260825-r1`.
The tracked result is
`experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4kxl-q8-tp1-exact-depth-result.json`.

| Active context | Decode tok/s | Prefill tok/s |
| ---: | ---: | ---: |
| 0 | 23.122116 | 759.033298 |
| 2,048 | 21.447833 | 731.081733 |
| 4,096 | 20.178749 | 714.545011 |
| 8,192 | 17.991709 | 685.254801 |
| 16,384 | 14.383417 | 634.601362 |
| 24,576 | 12.092596 | 592.443936 |
| 32,768 | 10.425173 | 557.748574 |

This is raw-engine target-only llama.cpp/SYCL evidence for the exact
UD-Q4_K_XL, TP1, MTP0, graph-off, q8_0-KV identity. It is not an HTTP serving
metric and adds no new quality claim. Existing quality evidence remains
separate.

The frozen grade-D estimates were uniformly conservative: every measured
decode point was 6.858% to 7.374% higher. The estimate snapshot remains in
Git as historical/calibration evidence, but it no longer owns these seven
public matrix cells.

No historical or featured speed changed. In particular, the vLLM graph
30.3298/49.0589/71.9002 TP-scale values remain separate and immutable.
