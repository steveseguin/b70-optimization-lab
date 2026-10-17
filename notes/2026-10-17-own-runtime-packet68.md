# Packet 68: depth-2 MTP

The design is committed before implementation. The current engine verifies
one target row at a time. Its measured costs do not establish the claimed
56.6 tok/s estimate: that proxy assumes verifier savings that have never
been measured.

The chosen first prototype keeps the exact target row path and uses two
draft proposals across two pipeline intervals. Its simple cost estimate is
about 50.15 tok/s, not an improvement claim. The device probe will measure
the extra speculative half and restore cost before the coordinator tests
the prototype. A shared-weight M=3 verifier remains a larger, separate arm.

All work here is CPU-only, confined to the new packet and this requested
note. The frozen trees and CURRENT.md remain with their owners.

[Design](../experiments/own-xpu-runtime/stage2/packet68-mtp-depth2/DESIGN.md).
