# R189: 2K-32K real-content depth curve on the R187 line (whole-graph compile)

Date: 2026-09-03 21:54-22:07 EDT, boot 88f0984f (clean). R156 image via the R187 wrappers
(`COMPILATION_CONFIG splitting_ops=[]`), capacity 33,024 tokens, one slot, 4,096-token chunked prefill; the R150
protocol (three real-content classes, three requests per depth, 128 output tokens, cache zero, canaries). Prereg
`data/2026-09-03-qwen38-fp8-r187-real-content-depth-r189-prereg.json`; result
`data/2026-09-03-qwen38-fp8-r187-real-content-depth-r189-result.json`.

| active context | MTP1 decode (R150) | MTP1 TTFT | MTP0 decode (R150) | MTP0 TTFT | MTP1 = MTP0 |
| ---: | ---: | ---: | ---: | ---: | :---: |
| 2048 | 54.61 (54.81) | 0.60 s | 33.00 (33.36) | 0.58 s | yes |
| 4096 | 55.17 (55.45) | 1.17 s | 32.74 (32.98) | 1.14 s | yes |
| 8192 | 53.74 (54.14) | 2.37 s | 31.90 (32.11) | 2.33 s | yes |
| 16384 | 52.68 (53.05) | 4.95 s | 31.18 (31.41) | 4.83 s | yes |
| 24576 | 51.56 (52.88) | 7.74 s | 30.45 (30.62) | 7.55 s | yes |
| 32768 | 51.55 (51.93) | 10.72 s | 29.78 (29.96) | 10.44 s | yes |

Reading: the whole-graph compile keeps the long-context profile of the piecewise line within measurement noise
(the largest gap, 24K MTP1 at -2.5%, is a single three-sample median) and keeps MTP1 lossless against MTP0 at
every depth. Published as the R187 line's depth profile (package performance profiles, guide table).
