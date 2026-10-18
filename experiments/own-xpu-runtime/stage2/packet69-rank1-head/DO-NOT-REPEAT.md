# Packet69 decisions

| Arm or method | Outcome / next condition |
| --- | --- |
| Infer target-head time from packet64 remainder | Impossible: missing observation sites. Run the sealed measurement copy. |
| Prefix roofline from GGUF bytes alone | Wrong read-byte basis; expanded Q6_K reads 3,200 code/scale bytes per row, with a 3,380-byte storage stride. |
| Use 3,200 useful head bytes as row stride | Reproduced CPU failure at row 1: BF16 NaN, then production argmax sticky error. Revision 3 derives 3,380-byte stride from the existing layout helper; multi-row linked fixtures required. Device rerun pending. |
| Reopen packet52 target free-order grid for draft | Its format-specific losses do not establish draft speed. Reuse existing deterministic draft kernels instead. |
| Fused argmax campaign first | Deferred: only about 21 µs, little return relative to draft attention/HC. Target argmax remains untouched. |
| Target wide64/wide128, draft head/attention/HC | CPU checks pass; device comparisons pending. Do not call them winners yet. |
| CPU report retains a drained lane marker | Closed by pre-drain receipt staging and postflight release before aggregation; injected failure tests pass. |

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
[Revision-3 stride repair closeout](STRIDE-REPAIR-CLOSEOUT.md).
