# Qwen3.8 AutoRound INT4 native-GDN TP1 R8 result

Date: 2026-08-31

Status: **rejected; 7/12 exact fresh-server repeat**

The model fit one B70 (16.6 GiB model allocation) and both full strict arms
passed their workload and canary gates at 30.4094 and 30.4617 tok/s. This is
only about 4.7% below the R6 two-card diagnostic rate and is potentially useful
deployment efficiency, but the output gate failed.

Only 7/12 complete token arrays matched. The mismatches were
`benchmark-analysis`, `decision-memo`, `performance-hypotheses`,
`release-plan`, and `sql-debugging`. This proves the remaining nondeterminism
is rank-local; TP2 collectives and sharding are not required to trigger it.
Both rates remain quarantined, full quality is not authorized, and MTP remains
blocked.

The prior production-shape cross-process INT4 screen covered only M=65. The
next bounded diagnostic fills the actual MTP0 surfaces: M=1 decode plus all 12
realistic-suite prefill row counts (48--78) across fresh processes. This must
precede more model-level synchronization or compilation experiments.

Structured result:
`../data/2026-08-31-qwen38-autoround-native-gdn-tp1-r8-result.json`.
