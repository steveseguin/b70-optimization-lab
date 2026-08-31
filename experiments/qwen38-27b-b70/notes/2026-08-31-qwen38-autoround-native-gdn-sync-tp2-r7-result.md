# Qwen3.8 AutoRound INT4 native-GDN synchronization TP2 R7 result

Date: 2026-08-31

Status: **rejected; 8/12 exact fresh-server repeat**

Correction (2026-08-31): the pinned image does not implement
`VLLM_XPU_GDN_SYNC_AFTER_NATIVE`; the recorded environment variable was inert.
R7 is a valid second native-path repeatability measurement, not an engaged
synchronization treatment. The sync causal conclusion below is withdrawn.

Both native-GDN synchronization arms passed their complete realistic workload
and canary gates at 32.1748 and 31.7531 tok/s. The treatment had no useful
performance cost, but the output gate worsened from R6's 10/12 to 8/12. The
four mismatches were `code-review`, `performance-hypotheses`, `release-plan`,
and `sql-debugging`.

This rejects the candidate parent on repeatability only. It does not test or
reject a GDN synchronization fix. The rates are diagnostic-only and no quality
or MTP stage is authorized.

The next localization control uses the same image/model/flags with TP1 on one
local B70. Exact TP1 repeat would isolate the remaining defect to TP2; TP1
divergence would instead implicate a rank-local numerical path.

Structured result:
`../data/2026-08-31-qwen38-autoround-native-gdn-sync-tp2-r7-result.json`.
