# Qwen3.8 AutoRound INT4 native-GDN synchronization TP2 R7 result

Date: 2026-08-31

Status: **rejected; 8/12 exact fresh-server repeat**

Both native-GDN synchronization arms passed their complete realistic workload
and canary gates at 32.1748 and 31.7531 tok/s. The treatment had no useful
performance cost, but the output gate worsened from R6's 10/12 to 8/12. The
four mismatches were `code-review`, `performance-hypotheses`, `release-plan`,
and `sql-debugging`.

This rejects synchronization immediately after ordinary native GDN as a
correctness fix. The rates are diagnostic-only, no quality or MTP stage is
authorized, and the sync treatment must remain off.

The next localization control uses the same image/model/flags with TP1 on one
local B70. Exact TP1 repeat would isolate the remaining defect to TP2; TP1
divergence would instead implicate a rank-local numerical path.

Structured result:
`../data/2026-08-31-qwen38-autoround-native-gdn-sync-tp2-r7-result.json`.
