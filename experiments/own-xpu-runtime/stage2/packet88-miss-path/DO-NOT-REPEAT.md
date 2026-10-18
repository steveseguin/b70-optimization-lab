# Packet88 boundaries

| Date | Arm or interpretation | Outcome and revisit condition |
| --- | --- | --- |
| 2026-10-18 | Create R/D overlap by moving rank0 restore to BCS | Cross-card overlap already exists: 0.569325 ms of 0.569390 ms R. Revisit transport only with isolated copy timings and an end-to-end saving, not the same overlap argument. |
| 2026-10-18 | A minus C as copy time | Invalid: snapshot setup is outside the busy timer, waits differ, and instrumentation changes the sample. Flat restore has no registered device timer. |
| 2026-10-18 | Reuse wrong-token layers during correction | No unchanged-input layer proved. Embedding/PLE and all downstream activations depend on the corrected token. Static weights and command bindings are already reused. |
| 2026-10-18 | Remove remaining restore work without state proof | Existing spare-bank proof already saves 29,601,792 bytes. Preserve scratch tails, metadata, cancellation, abandoned redo and terminal observability. |
| 2026-10-18 | Treat 3.157 ms corrected enqueue time as serial overhead | Invalid: device work overlaps enqueue. Require measured exposed gaps before building a launch-overhead candidate. |
| 2026-10-18 | Attribute packet77 times to packet84 | Different host/kernel selections; packet84 is a prospective source parent, not the measured runtime here. |

Depth two, draft relocation and draft bytes remain closed under their existing
packet decisions. [Attribution](MISS.md), [closeout](CLOSEOUT.md).
