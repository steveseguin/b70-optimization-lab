# Packet67 negative findings

| Arm or method | Evidence and decision | Revisit condition |
| --- | --- | --- |
| HC virtual tree without exceptional fallback | GNU fixture failed NaN payload identity. [Receipt](evidence/failed-hc-virtualization.json), [exact failed source](evidence/failed-hc-before-fallback.hpp). Preserve and reject; no tolerance. | Only with a byte-exact exceptional path; current candidate uses original SG32 arithmetic. |
| Serial duplicated HC sigmoid epilogue | Offline compiler showed elevated flag spill metadata. [Pre-change report](evidence/registers-before-shared-epilogue.json). Replaced by four stream leaders while retaining sum order. No device speed verdict. | Compare actual device composition if current candidate fails. |
| Treating mixed-stage label medians as whole-call time | Attention, route, moe and QSA attention labels have multiple kernels. [Audit](ROOFLINE.md). | Sum events per invocation before taking medians. |
| Tuning QKV/Z/Q-gate as first priority | Useful-byte rates already about 500–511 GB/s; much less headroom than recurrence/HC. | New traffic/counter evidence or a larger arithmetic-preserving mechanism. |

The CPU preparation closes here; the optimization lane remains open. Device screens are the next gate.

| 2026-10-17 | packet67 HC four-stream geometry (hc-a/hc-f), recurrence shared-head (rec-head), combined | all slower in engine (-6% to -22%) on lane B, 13/13 exact | roofline-excess selection without in-engine bandwidth evidence; HC spill pressure | do not repeat without measured in-engine GB/s per site |
