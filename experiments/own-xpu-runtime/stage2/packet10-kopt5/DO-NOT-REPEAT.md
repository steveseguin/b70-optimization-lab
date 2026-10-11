# Round 5 closed assumptions

| Assumption | Evidence | Revisit condition |
| --- | --- | --- |
| IQ2/3 direct signed values fit four bits | IQ2 max43, IQ3_S max15, XXS max62; normative grids | Different encoding with explicit lookup/reconstruction cost |
| Full expansion fits two cards | 157.954 GB weights in analysis.json | Larger topology or different exact layout |
| All IQ2 experts fit expanded | 131.583 GB weights with dense expansion | Different layout or explicitly bounded subset policy |
| Head is F16 and 1.27 GB | Census: Q6_K, 521,472,000 packed bytes | New authenticated checkpoint |
| FMA preserves separate FP32 multiply/add | Different rounding point | Owner-approved arithmetic identity with full quality gate |
| Unsplit and split4 are the same reduction | Distinct declared lane/tile trees | Complete-model identity evidence |
| 119 tok/s is expanded-layout ceiling | Old 4.951 GB packed payload | Recompute byte floor for the actual candidate |

| Runtime-type dequant tests cover a specialized exceptional-scale GEMV | IQ3_S CPU row 23 flips NaN sign; [repair](exactness-repair.json) | Require specialized GEMV against packed/materialized bits, then a fresh device gate |

[CPU closeout](CLOSEOUT.md). The original device gate failed exactness; repaired device qualification remains pending.
