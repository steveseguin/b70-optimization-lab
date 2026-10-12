| Kernel | SIMD | Static inst / messages | 64-bit typed inst | int→float | SLM / barrier | Spill B | Scratch B/HW thread | Private B/HW thread | Cross-thread payload B | Pre-branch inst / backedges | Inner inst / messages per 8 lane weights |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| down R5 IQ4 | 32 | 2236 / 78 | 264 | 54 | 2 / 3 | 0 | 0 | 5888 | 196 | 69 / 18 | 475 / 25 |
| down p25.private_decode | 32 | 1969 / 83 | 258 | 55 | 6 / 3 | 0 | 0 | 256 | 160 | 23 / 11 | unestablished |
| down p27.packed64 | 32 | 1895 / 55 | 330 | 55 | 6 / 3 | 0 | 0 | 0 | 152 | 14 / 4 | unestablished |
| down p25.wide8 | 32 | 1572 / 55 | 226 | 55 | 6 / 3 | 0 | 0 | 0 | 152 | 14 / 4 | unestablished |
| down p27.fp32_input | 32 | 2053 / 83 | 246 | 55 | 6 / 3 | 0 | 0 | 256 | 160 | 23 / 11 | unestablished |
| down p28.shared.wg32 | 32 | 966 / 63 | 140 | 33 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 3 | unestablished |
| down p29.wg32 | 32 | 737 / 51 | 83 | 24 | 0 / 0 | 0 | 0 | 0 | 56 | 24 / 3 | 169 / 15 |
| down p29.rows4 | 32 | 738 / 51 | 83 | 24 | 0 / 0 | 0 | 0 | 0 | 56 | 25 / 3 | unestablished |
| gate R5 IQ2 | 32 | 2686 / 87 | 363 | 71 | 2 / 3 | 0 | 0 | 5888 | 196 | 70 / 18 | unestablished |
| gate p28.private.wg32 IQ2 | 32 | 1796 / 76 | 156 | 105 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 6 | unestablished |
| gate p28.shared.wg32 IQ2 | 32 | 1640 / 60 | 100 | 105 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 6 | unestablished |
| gate p28.paired.wg32 IQ2 | 32 | 982 / 34 | 73 | 57 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 3 | unestablished |
| gate p25.half_table IQ2 | 32 | 2799 / 202 | 437 | 64 | 6 / 3 | 1728 | 2048 | 256 | 160 | 31 / 10 | unestablished |
| gate p25.paired_input IQ2 | 32 | 2716 / 184 | 364 | 72 | 6 / 3 | 2560 | 4096 | 256 | 160 | 33 / 11 | unestablished |
| gate R5 IQ3 | 32 | 2702 / 91 | 374 | 79 | 2 / 3 | 0 | 0 | 5888 | 196 | 69 / 18 | unestablished |
| gate p28.private.wg32 IQ3 | 32 | 1879 / 76 | 181 | 105 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 6 | unestablished |
| gate p28.shared.wg32 IQ3 | 32 | 1724 / 60 | 125 | 105 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 6 | unestablished |
| gate p28.paired.wg32 IQ3 | 32 | 1032 / 34 | 88 | 57 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 3 | unestablished |
| gate p25.half_table IQ3 | 32 | 2773 / 192 | 435 | 72 | 6 / 3 | 2048 | 2048 | 256 | 160 | 31 / 10 | unestablished |
| gate p25.paired_input IQ3 | 32 | 2965 / 270 | 377 | 80 | 6 / 3 | 7808 | 8192 | 256 | 160 | 33 / 11 | unestablished |
| dense R5 SG32/split4 Q6 | 32 | 1151 / 32 | 129 | 46 | 2 / 3 | 0 | 0 | 0 | 81 | 14 / 8 | unestablished |
| dense p28.wg32 Q6 split1 | 32 | 353 / 12 | 32 | 11 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 2 | unestablished |
| dense p28.wg32 Q6 split4 | 32 | 353 / 12 | 33 | 11 | 0 / 0 | 0 | 0 | 0 | 120 | 20 / 2 | unestablished |
| dense p28.rows4 Q6 split1 | 32 | 420 / 14 | 42 | 12 | 0 / 3 | 0 | 0 | 0 | 120 | 18 / 2 | unestablished |
| dense p28.rows4 Q6 split4 | 32 | 467 / 18 | 43 | 12 | 4 / 3 | 0 | 0 | 0 | 128 | 21 / 2 | unestablished |
| dense p25.scale8 Q6 | 32 | 1411 / 39 | 192 | 55 | 6 / 3 | 0 | 0 | 0 | 152 | 14 / 2 | unestablished |
| dense R5 SG32/split4 Q8 | 32 | 1151 / 32 | 129 | 46 | 2 / 3 | 0 | 0 | 0 | 81 | 14 / 8 | unestablished |
| dense p28.wg32 Q8 split1 | 32 | 353 / 12 | 32 | 11 | 0 / 0 | 0 | 0 | 0 | 120 | 17 / 2 | unestablished |
| dense p28.wg32 Q8 split4 | 32 | 353 / 12 | 33 | 11 | 0 / 0 | 0 | 0 | 0 | 120 | 20 / 2 | unestablished |
| dense p28.rows4 Q8 split1 | 32 | 420 / 14 | 42 | 12 | 0 / 3 | 0 | 0 | 0 | 120 | 18 / 2 | unestablished |
| dense p28.rows4 Q8 split4 | 32 | 467 / 18 | 43 | 12 | 4 / 3 | 0 | 0 | 0 | 128 | 21 / 2 | unestablished |
| dense p25.scale8 Q8 | 32 | 1411 / 39 | 192 | 55 | 6 / 3 | 0 | 0 | 0 | 152 | 14 / 2 | unestablished |
| route specialised (5 stages) | 32 | 4749 / 384 | 530 | 83 | 0 / 0 | 0 | 32768 | 22528 | 768 | 858 / 1 | unestablished |
| route round2 (3 stages) | 32 | 5231 / 469 | 378 | 8 | 128 / 150 | 0 | 0 | 0 | 88 | 96 / 8 | unestablished |
| QSA packet18 / activation / GDN native fixture | 32 | 12241 / 513 | 612 | 229 | 122 / 180 | 0 | 32768 | 21504 | 204 | 52 / 85 | unestablished |
| QSA/GDN packet18 production adapter | 32 | 29282 / 1643 | 4275 | 1055 | 167 / 228 | 0 | 65536 | 45312 | 772 | 184 / 155 | unestablished |
| round2 score | 32 | 547 / 87 | 19 | 18 | 40 / 36 | 0 | 0 | 0 | 192 | 16 / 1 | unestablished |
| round2 softmax | 32 | 754 / 41 | 19 | 13 | 9 / 21 | 0 | 0 | 0 | 192 | 18 / 5 | unestablished |
| round2 value | 32 | 735 / 34 | 22 | 13 | 7 / 15 | 0 | 0 | 0 | 192 | 18 / 4 | unestablished |
| round2 GDN recurrence | 32 | 2825 / 24 | 35 | 17 | 0 / 0 | 0 | 0 | 0 | 184 | 14 / 1 | unestablished |
| small.hc | 32 | 1147 / 62 | 222 | 8 | 4 / 6 | 0 | 0 | 0 | 80 | 8 / 1 | unestablished |
| NEW down.bank | 32 | 843 / 27 | 40 | 33 | 0 / 0 | 0 | 0 | 0 | 120 | 12 / 3 | 188 / 7 |
| NEW down.select | 32 | 1757 / 57 | 138 | 33 | 0 / 0 | 0 | 0 | 0 | 120 | 12 / 3 | [290, 306, 482] / 17 |
| NEW gate.restrict IQ2 | 32 | 926 / 34 | 68 | 57 | 0 / 0 | 0 | 0 | 0 | 120 | 12 / 3 | unestablished |
| NEW gate.restrict IQ3 | 32 | 977 / 34 | 83 | 57 | 0 / 0 | 0 | 0 | 0 | 120 | 12 / 3 | unestablished |
| NEW dense.segment Q6 split1 | 32 | 318 / 13 | 15 | 17 | 0 / 0 | 0 | 0 | 0 | 120 | 12 / 1 | unestablished |
| NEW dense.segment Q6 split4 | 32 | 406 / 23 | 57 | 17 | 0 / 0 | 0 | 0 | 0 | 120 | 14 / 0 | unestablished |
| NEW dense.segment Q8 split1 | 32 | 318 / 13 | 15 | 17 | 0 / 0 | 0 | 0 | 0 | 120 | 12 / 1 | unestablished |
| NEW dense.segment Q8 split4 | 32 | 406 / 23 | 57 | 17 | 0 / 0 | 0 | 0 | 0 | 120 | 14 / 0 | unestablished |
| NEW route.rank4 | 32 | 3051 / 349 | 138 | 8 | 128 / 150 | 0 | 0 | 0 | 88 | 96 / 8 | unestablished |
| NEW QSA.shape score | 32 | 465 / 87 | 19 | 0 | 40 / 36 | 0 | 0 | 0 | 200 | 16 / 1 | unestablished |
| NEW QSA.shape softmax | 32 | 733 / 42 | 19 | 13 | 9 / 21 | 0 | 0 | 0 | 200 | 18 / 5 | unestablished |
| NEW QSA.shape value | 32 | 722 / 34 | 22 | 13 | 7 / 15 | 0 | 0 | 0 | 200 | 18 / 4 | unestablished |
