# Packet64 in-engine attribution

Diagnostic only. All times below are microseconds.

| Rank | Type | Speculative | Class | Measured mean / operation | Scaled estimate |
| --- | --- | --- | --- | ---: | ---: |
| 0 | GDN | False | attention | 207.02 | 197.41 |
| 0 | GDN | False | hc_norm_merge | 88.90 | 84.78 |
| 0 | GDN | False | moe_experts | 194.64 | 185.60 |
| 0 | GDN | False | shared_expert | 15.11 | 14.41 |
| 0 | GDN | True | attention | 206.97 | 197.36 |
| 0 | GDN | True | hc_norm_merge | 88.79 | 84.67 |
| 0 | GDN | True | moe_experts | 194.97 | 185.92 |
| 0 | GDN | True | shared_expert | 15.11 | 14.41 |
| 0 | QSA | False | attention | 223.05 | 212.70 |
| 0 | QSA | False | hc_norm_merge | 89.56 | 85.41 |
| 0 | QSA | False | moe_experts | 194.07 | 185.06 |
| 0 | QSA | False | shared_expert | 15.54 | 14.82 |
| 0 | QSA | True | attention | 223.69 | 213.31 |
| 0 | QSA | True | hc_norm_merge | 89.57 | 85.41 |
| 0 | QSA | True | moe_experts | 194.22 | 185.20 |
| 0 | QSA | True | shared_expert | 15.43 | 14.72 |
| 1 | GDN | False | attention | 207.44 | 197.81 |
| 1 | GDN | False | hc_norm_merge | 90.92 | 86.70 |
| 1 | GDN | False | moe_experts | 197.16 | 188.01 |
| 1 | GDN | False | shared_expert | 15.52 | 14.80 |
| 1 | QSA | False | attention | 227.03 | 216.50 |
| 1 | QSA | False | hc_norm_merge | 88.76 | 84.64 |
| 1 | QSA | False | moe_experts | 195.57 | 186.50 |
| 1 | QSA | False | shared_expert | 15.21 | 14.51 |
| 1 | draft | False | argmax | 21.05 | 20.61 |
| 1 | draft | False | attention | 388.11 | 380.03 |
| 1 | draft | False | embedding_ple | 61.46 | 60.18 |
| 1 | draft | False | hc_norm_merge | 337.05 | 330.03 |
| 1 | draft | False | head_prefix | 521.30 | 510.45 |
| 1 | draft | False | moe_experts | 251.33 | 246.10 |
| 1 | draft | False | other | 5.93 | 5.80 |
| 1 | draft | False | shared_expert | 44.14 | 43.22 |
| 1 | draft | False | transfers | 2.80 | 2.74 |

| Half | Control mean | Instrumented mean | Measured outside layers |
| --- | ---: | ---: | ---: |
| rank0_speculative | 14232.54 | 14893.85 | 2346.34 |
| rank0_corrected | 12992.11 | 13638.63 | 1102.49 |
| rank1_target | 14685.54 | 15441.21 | 3080.80 |

Ranked cost buckets (overlapping roles; not additive savings):

| Order | Rank / role | Type / class | Estimated cost |
| ---: | --- | --- | ---: |
| 1 | 1 / target_half | GDN / attention | 3560.57 |
| 2 | 0 / target_half | GDN / attention | 3553.45 |
| 3 | 0 / speculative_half | GDN / attention | 3552.54 |
| 4 | 1 / target_half | GDN / moe_experts | 3384.27 |
| 5 | 0 / speculative_half | GDN / moe_experts | 3346.61 |
| 6 | 0 / target_half | GDN / moe_experts | 3340.85 |
| 7 | 1 / rank1_target | outside_layers / remainder | 2937.83 |
| 8 | 0 / rank0_speculative | outside_layers / remainder | 2237.46 |
| 9 | 1 / target_half | GDN / hc_norm_merge | 1560.58 |
| 10 | 0 / target_half | GDN / hc_norm_merge | 1525.96 |
| 11 | 0 / speculative_half | GDN / hc_norm_merge | 1524.03 |
| 12 | 1 / target_half | QSA / attention | 1298.98 |
| 13 | 0 / speculative_half | QSA / attention | 1279.87 |
| 14 | 0 / target_half | QSA / attention | 1276.17 |
| 15 | 1 / target_half | QSA / moe_experts | 1118.99 |
| 16 | 0 / speculative_half | QSA / moe_experts | 1111.22 |
| 17 | 0 / target_half | QSA / moe_experts | 1110.37 |
| 18 | 0 / rank0_corrected | outside_layers / remainder | 1051.33 |
| 19 | 0 / speculative_half | QSA / hc_norm_merge | 512.46 |
| 20 | 0 / target_half | QSA / hc_norm_merge | 512.44 |
| 21 | 1 / draft | draft / head_prefix | 510.45 |
| 22 | 1 / target_half | QSA / hc_norm_merge | 507.86 |
| 23 | 1 / draft | draft / attention | 380.03 |
| 24 | 1 / draft | draft / hc_norm_merge | 330.03 |
| 25 | 1 / target_half | GDN / shared_expert | 266.43 |
| 26 | 0 / speculative_half | GDN / shared_expert | 259.39 |
| 27 | 0 / target_half | GDN / shared_expert | 259.35 |
| 28 | 1 / draft | draft / moe_experts | 246.10 |
| 29 | 0 / target_half | QSA / shared_expert | 88.92 |
| 30 | 0 / speculative_half | QSA / shared_expert | 88.30 |
| 31 | 1 / target_half | QSA / shared_expert | 87.05 |
| 32 | 1 / draft | draft / embedding_ple | 60.18 |
| 33 | 1 / draft | draft / shared_expert | 43.22 |
| 34 | 1 / draft | draft / argmax | 20.61 |
| 35 | 1 / draft | draft / other | 5.80 |
| 36 | 1 / draft | draft / transfers | 2.74 |

Target classes multiply paired sampled control/instrumented cycle median ratio; draft uses paired D-wall ratio. Estimates only.

- One loaded pair; fixed control-then-attribution order. No independent fresh-server speed verdict.
- Representative class totals extrapolate 18 GDN + 6 QSA per half; these are estimates, not measurements of every layer.
- Outside-layer duration subtracts a same-card layer span from its host half command duration. It is not GPU idle; scaled values are estimates and negative residuals remain visible.
- Class names follow surviving fused launch labels; mixed fused kernels cannot be split into original operator costs.
- Partial cancelled layers excluded from class means; rank0 corrected work occurs only on misses.
- Rank host times share the monotonic clock; GPU timestamps are never compared across cards.
- No prompt/KV/response reuse, but repeated full-suite control/observation is diagnostic only.
- Co-running lane A may affect costs; this is lever screening, never headline throughput.
