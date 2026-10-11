# Screen 1b — do not repeat

| Date | Closed arm / finding | Required next condition |
| --- | --- | --- |
| 2026-10-11 | Do not retry the v4 unmodified profile or resize alignment buffers for its raw `topk_ids=-1` failure. All four hashes are padding sentinels from V2/native routing, before alignment/remap; the one-rank hand-built valid-ID probe cannot cover it. | Use the [sealed production router fix with boundary ON](overlay-moe-boundary/README.md) and fresh coordinator admission. The v5 startup profile now passes; generation/output gates remain open. [Evidence/closeout](overlay-fix-router-padding/root-cause-closeout.md). |
| 2026-10-11 | Fourth incident closed: router-padding fix completes one TP4 startup profile under the strict boundary, zero violations/new faults and exit 0; no generation. Do not rerun unmodified v4 or call the v5 load-only command a generation screen. | Prepare a separately bounded boundary-on generation screen; resolve unknown VRAM reserves and output gates. A367 calibration still needs its own approved floor. [Closure and proof](../../../notes/2026-10-11-fourth-incident-closed.md). |
