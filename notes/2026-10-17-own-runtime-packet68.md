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

## Probe milestone

The cost probe is **sealed and pushed; the coordinator can run it now while
prototype CPU work continues**. Its build is 118 MB. Host/device builds, the
six-row synthetic target byte comparison against packet64, discarded-state
restoration, fresh repeats, the lean seal and lane-B plan pass. No GPU ran.

Command: `bash experiments/own-xpu-runtime/stage2/packet68-mtp-depth2/coordinator_probe.sh "$FAULT_REVIEW"`
inside an admitted coordinator `screen-*` unit with approved `P49_LDP`.
Expect roughly five minutes active, with a 3600-second watchdog. It uses
23/25 because that is the frozen wrapper's admitted lean-lineage placement.
All thirteen token checks remain mandatory. [Probe details](../experiments/own-xpu-runtime/stage2/packet68-mtp-depth2/PROBE.md).
