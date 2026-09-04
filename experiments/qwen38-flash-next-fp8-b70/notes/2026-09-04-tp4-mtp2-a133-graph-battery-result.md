# A133: MTP2 on the deterministic graph line is lossless too (2026-09-04, 10:10-10:34)

The A113 identity with two speculative tokens (`num_speculative_tokens` 2,
capture sizes [1, 2, 3], KV 376569856) and the three exact-verify selectors
at three rows (`VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1`,
`VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=3`, `VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=3`)
on overlay 5915cb0e; diagnostic battery, first launch after the 09:42 reset.

| gate | A133 (graph MTP2) | A113 (graph MTP1) | MTP0 line |
|---|---|---|---|
| short p146/o256, tok/s | `32.21 / 37.03 / 32.00`, median `32.21` | `31.20 / 34.73 / 31.31` | center `22.66` |
| short hash | `5f407446...` (= MTP0) | same | same |
| exact 2K, 99-interval tok/s (TTFT s) | `8.09 / 7.37` (150.2 / 106.0) | `8.55 / 8.47` | `13.99` |
| exact 2K hash | `afffd211...` (= MTP0) | same | same |
| exact 4K, 99-interval tok/s (TTFT s) | `7.37 / 7.30` (180.0 / 153.3) | `7.69 / 7.27` | `12.78` |
| exact 4K hash | `c6193cc6...` (= MTP0) | same | same |
| quality | 6/7 (`code_execution=30`), 16/16 `3b0b3192...`, exact needle | same | same |
| draft acceptance | 984 of 1122 tokens (position 0: 519/561, position 1: 465/561) | 735/785 | |

No trace work was needed: the three selectors generalize to three verifier
rows (the serial GDN path loops over any number of rows; the row-wise
all-reduce and norm take the max-rows count). MTP2 is 1.42x the MTP0 line
at short context in the battery, marginally above MTP1 (1.38x), and sits in
the same depth band (0.55x at 2K), so the two-row/three-row graph replay
cost is again the limiter. Data:
`../data/20260904-tp4-mtp2-a133-graph-three-flags-battery.json`.
