# Screen 1b — do not repeat

| Date | Closed arm / finding | Required next condition |
| --- | --- | --- |
| 2026-10-11 | Do not retry the v4 unmodified profile or resize alignment buffers for its raw `topk_ids=-1` failure. All four hashes are padding sentinels from V2/native routing, before alignment/remap; the one-rank hand-built valid-ID probe cannot cover it. | Use the [sealed production router fix with boundary ON](overlay-moe-boundary/README.md) and fresh coordinator admission. Native startup and output gates remain open. [Evidence/closeout](overlay-fix-router-padding/root-cause-closeout.md). |
