# Packet76 boundaries

| Method or arm | Outcome / next condition |
| --- | --- |
| Treat the 1.61 ms as device idle | Invalid: most is host housekeeping and observation overhead. See ATTRIBUTION.md. |
| Subtract copy and compute clocks | Refused: sampled copies have a repeated zero-width timestamp. No valid latency inference. |
| Charge rank0 handover or mailbox arrival to rank1's received-to-completed half | Wrong boundary: handover and arrival precede that interval. |
| Infer late issue from host enqueue duration | Unsupported without per-submit timing and clock correlation; enqueue overlaps device work. |
| Graph replay as the first fix | Deferred: measured sampled device gaps are small; target host cleanup first. Packet34's old neutral result is not a current-speed verdict. |
| Call ordered retirement a winner from CPU checks | Not measured; coordinator runs the pinned A grid and only its exact improving B winner. |
| Force new 24/24 lineage into shared v4 | Refused; supported 23/25 used for both arms. Actual 24/24 refusal retained. |
| CPU allocation mock with overlapping fake logical ranges | Test scaffolding rejected by the real p39 alias guard; use disjoint logical device addresses, real small pinned buffers and no payload execution. |

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
