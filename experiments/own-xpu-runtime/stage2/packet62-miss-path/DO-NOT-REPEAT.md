# Packet62 boundaries

| Closed question | Evidence and condition to revisit |
| --- | --- |
| Use packet57's rank0-last percentage as current bottleneck | Packet61 A/B now have rank0 last in 1/1574 and 0/1574 cycles; rerun attribution after a changed configuration. |
| Claim removal of the whole 11.4 ms miss penalty from rollback | Current rollback is only about 0.74 ms; corrected work is about 12.51 ms and remains required. |
| Blindly swap workspace, scratch or QSA allocations | Historical tails/committed rows remain observable. Require a complete exact tail/read-write proof first. |
| Swap logical allocation IDs without changing prepared commands | Prepared pointer captures remain bound to old allocations. Six prepared recurrent pairs are retained. |
| Claim bank rotation removes confirmed-redo bank restores | Packet61 already omits those 29.6 MB. The new saving is capture and terminal/fallback rollback traffic. |
| Rank controller dispatch as a large miss lever | Current verify-to-rollback and rollback-to-redo gaps are about 12 us and 1.5 us. Only host bookkeeping overlap is prepared. |

Do not change a selection, binary or source after sealing. Do not edit packet61,
packet61x or the shared screen wrapper. CPU tests and `--plan` do not qualify
speed or production device output. The coordinator owns every device window,
fault review and teardown. [CPU closeout](CPU-PREPARATION-CLOSEOUT.md).
