# Packet82 boundaries

| Arm / method | Evidence and decision | Revisit condition |
| --- | --- | --- |
| Separate shared-head prepass | Packet67 rec-head lost 11.8%, combined 21.8%; closes that mechanism. | New evidence removing its launch/dependency cost. |
| More groups as an occupancy cure | Production already has 1,536 groups for 32 cores. | Actual occupancy/stall evidence. |
| Approximate gate math, reordered reductions, FP32 state carry | Changes the arithmetic identity; excluded. | Owner's separately labeled quality decision. |
| Tiny startup mock | Insufficient; real full-shape post-load allocations and captured selected operations required. | None. |
| Cross-compiler NaN normalization | Forbidden. Compare every raw candidate byte to its own compiler's production; record existing GNU/Intel production payload differences separately. | A separately qualified arithmetic identity. |
| CPU or offline result as device speed | No device ran here. | Coordinator's exact A/B screens and subsequent full promotion gates. |

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
