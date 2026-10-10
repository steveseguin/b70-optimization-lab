# Planned grids versus actual UD tensors

Exact bytes; arithmetic only. “Planned” preserves STAGE2-PLAN’s homogeneous
grid and official nonexpert floor. “Actual” uses all packed tensors from
the three real shards, offloads PLE/input embeddings and adds one HC
down/up replica. It is not a measured allocation. Actual files have **48
expert banks and no MTP**; planned totals included 49 banks plus MTP dense.

| Variant | Planned resident B | Actual resident B | Correction B | Headroom B | After KV + metadata B |
| --- | ---: | ---: | ---: | ---: | ---: |
| UD-IQ3_XXS | 57,321,436,698 | 53,304,619,520 | -4,016,817,178 | 15,179,976,192 | 14,426,836,200 |
| UD-IQ4_XS | 75,625,641,498 | 64,871,421,440 | -10,754,220,058 | 3,613,174,272 | 2,860,034,280 |
| UD-Q3_K_XL | 63,101,711,898 | 61,175,191,040 | -1,926,520,858 | 7,309,404,672 | 6,556,264,680 |

Capacity: **68,484,595,712 B**. KV scenario: **753,139,712 B**, full 16-bit.
PLE control metadata: **280 B**; extra replicas, state, graphs and working
space remain additional. No per-card fit is established by the balanced sum.

| Variant | Planned top10 experts B/token | Actual top10 experts B/token | Dense B/token | Selected lookup B/token | Actual total B/token |
| --- | ---: | ---: | ---: | ---: | ---: |
| UD-IQ3_XXS | 903,168,000 | 949,760,000 | 4,001,477,120 | 3,540 | 4,951,240,940 |
| UD-IQ4_XS | 1,253,376,000 | 1,162,496,000 | 4,676,195,840 | 4,160 | 5,838,696,280 |
| UD-Q3_K_XL | 1,013,760,000 | 1,090,304,000 | 4,676,195,840 | 4,160 | 5,766,504,280 |

Actual total = top10 experts + dense + selected lookups + 280 metadata bytes.
This is one target-only decode token, with each dense tensor once; it
excludes TP2 extra HC reads, KV/state traffic and collectives. TP2 HC
adds **675,430,400 B/token** in every variant. No MTP proposal rate exists.

| Variant | Planned all49 experts B | Same grid, 48 banks B | Actual all48 experts B | Planned nonexpert floor B | Actual nonexpert floor B |
| --- | ---: | ---: | ---: | ---: | ---: |
| UD-IQ3_XXS | 47,205,580,800 | 46,242,201,600 | 48,627,712,000 | 10,115,855,898 | 4,676,907,520 |
| UD-IQ4_XS | 65,509,785,600 | 64,172,851,200 | 59,519,795,200 | 10,115,855,898 | 5,351,626,240 |
| UD-Q3_K_XL | 52,985,856,000 | 51,904,512,000 | 55,823,564,800 | 10,115,855,898 | 5,351,626,240 |

Both nonexpert floors include the extra HC copy and exclude host PLE/input
embedding tables. The planned one includes MTP dense; the actual one cannot.

## Component tensor bytes

| Component | UD-IQ3_XXS | UD-IQ4_XS | UD-Q3_K_XL |
| --- | ---: | ---: | ---: |
| embedding | 521,472,000 | 675,430,400 | 675,430,400 |
| gdn | 1,754,576,384 | 2,247,243,264 | 2,247,243,264 |
| hyperconnections | 691,159,040 | 691,159,040 | 691,159,040 |
| native_mtp | 0 | 0 | 0 |
| norms | 4,028,416 | 4,028,416 | 4,028,416 |
| ple_lookup | 28,800,138,240 | 28,800,138,240 | 28,800,138,240 |
| ple_projection | 35,102,720 | 35,102,720 | 35,102,720 |
| qsa_attention | 490,291,200 | 635,043,840 | 635,043,840 |
| qsa_indexer | 39,321,600 | 39,321,600 | 39,321,600 |
| routed_experts | 48,627,712,000 | 59,519,795,200 | 55,823,564,800 |
| routers | 252,149,760 | 252,149,760 | 252,149,760 |
| shared_experts | 213,376,000 | 250,675,200 | 250,675,200 |
| target_head | 521,472,000 | 521,472,000 | 521,472,000 |
| vision_excluded | 0 | 0 | 0 |
| **Tensor total** | 81,950,799,360 | 93,671,559,680 | 89,975,329,280 |
| **GGUF file total** | 81,961,823,936 | 93,682,584,224 | 89,986,353,824 |
| **Unique fetched headers** | 11,024,519 | 11,024,519 | 11,024,519 |

Tensor totals include the host PLE/input tables. File totals add headers
and alignment padding. The fetch receipt separately counts the discarded
15,039-byte IQ3 discovery prefix, so transfer bytes exceed unique headers.

## Real expert grids by layer

| Variant | Projection | GGUF type | Zero-based layers |
| --- | --- | --- | --- |
| UD-IQ3_XXS | ffn_down_exps | IQ4_NL | all 0–47 |
| UD-IQ3_XXS | ffn_gate_exps | IQ2_S | 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47 |
| UD-IQ3_XXS | ffn_gate_exps | IQ3_S | 2 |
| UD-IQ3_XXS | ffn_up_exps | IQ2_S | 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47 |
| UD-IQ3_XXS | ffn_up_exps | IQ3_S | 2 |
| UD-IQ4_XS | ffn_down_exps | IQ4_NL | 0, 1, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45 |
| UD-IQ4_XS | ffn_down_exps | Q8_0 | 2, 4, 30, 46, 47 |
| UD-IQ4_XS | ffn_gate_exps | IQ3_S | 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47 |
| UD-IQ4_XS | ffn_gate_exps | IQ4_XS | 2 |
| UD-IQ4_XS | ffn_up_exps | IQ3_S | 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47 |
| UD-IQ4_XS | ffn_up_exps | IQ4_XS | 2 |
| UD-Q3_K_XL | ffn_down_exps | IQ4_NL | 0, 1, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45 |
| UD-Q3_K_XL | ffn_down_exps | Q8_0 | 2, 4, 30, 46, 47 |
| UD-Q3_K_XL | ffn_gate_exps | IQ3_XXS | 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47 |
| UD-Q3_K_XL | ffn_gate_exps | IQ4_XS | 2 |
| UD-Q3_K_XL | ffn_up_exps | IQ3_XXS | 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47 |
| UD-Q3_K_XL | ffn_up_exps | IQ4_XS | 2 |

## Nonexpert storage types

| Component | UD-IQ3_XXS | UD-IQ4_XS | UD-Q3_K_XL |
| --- | --- | --- | --- |
| embedding | Q6_K | Q8_0 | Q8_0 |
| gdn | F32, Q6_K, Q8_0 | F32, Q8_0 | F32, Q8_0 |
| hyperconnections | F32, Q8_0 | F32, Q8_0 | F32, Q8_0 |
| norms | F32 | F32 | F32 |
| ple_lookup | IQ4_NL | IQ4_NL | IQ4_NL |
| ple_projection | F32, Q8_0 | F32, Q8_0 | F32, Q8_0 |
| qsa_attention | Q6_K | Q8_0 | Q8_0 |
| qsa_indexer | BF16 | BF16 | BF16 |
| routers | F32 | F32 | F32 |
| shared_experts | Q6_K, Q8_0 | Q8_0 | Q8_0 |
| target_head | Q6_K | Q6_K | Q6_K |

Every tensor name behind these groups is in `nonexpert_type_inventory` in
[ud-census.json](ud-census.json). IQ3 remains first for capacity; IQ4’s
previous weight-only rejection is withdrawn. No quant quality ranking
or runtime qualification follows from these tables.
