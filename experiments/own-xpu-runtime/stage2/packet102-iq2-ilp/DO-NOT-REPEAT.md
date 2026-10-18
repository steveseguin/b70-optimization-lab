# Packet102 boundaries

Read packet65, 67, 73, 81, 90, 95 and 99 before opening these arms.
Do not reopen table relocation/compaction, E3 word prefetch, E2 scale cache,
four-stream HC geometry, all-span expert sweeps or packed activation reads.
This packet batches dependent grid reads and separately shares gate/up inputs.
Keep packet49 FP32 chains and trees, full half-cache layout and full BF16 KV.
No speed claim or model screen before the 15% device micro gate.
V5 expert switching is unavailable in its frozen native engine; use v4.

| Arm | Outcome | Revisit condition |
| --- | --- | --- |
| Shared V8 | 2,304–3,072 scratch bytes; rejected | A lower live-state design |
| Shared V4 duplicate output paths | Flag spills and scratch | Consolidated epilogue is the retained fix |
| V4 batch2/shared and batch4/shared | Exact, but still scratch spills; no micro/screen | Concrete lower-register composition |
| Per-kernel 256 GRFs | Offline stack rejects `SPV_INTEL_maximum_registers` | Separately qualified compiler support |

| Batch2 standalone | 1.89% lower micro kernel time; fails 15% gate | Materially different scheduling design |
| Batch4 standalone | 0.16% higher micro kernel time; fails gate | Materially different scheduling design |
| Shared input standalone | 3.31% higher micro kernel time; fails gate | Materially lower live state/overhead |

[Combined-arm closeout](COMBINED-CLOSEOUT.md) and
[coordinator micro closeout](MICRO-CLOSEOUT.md). No candidate reaches screens.
