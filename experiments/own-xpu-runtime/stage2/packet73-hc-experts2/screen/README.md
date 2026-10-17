# Packet73 private v4 screen

Copied from frozen stage2/screen/v4-lanes. Teardown refusal cooperatively stops
only this worker's ranks. Successful drain/postflight releases both leases
before reporting. Shared v3 teardown and lane-coordination roots are unchanged.

Lane A: production, hc-wide, experts2-a, experts2-b, combined, production.
Lane B: production, highest class-balanced exact A candidate, production.
All six A screens must be exact. The winner must exceed the two-control mean.
Ties follow A order. If no candidate improves, lane B refuses before launching.
Combined is HC plus experts2-b, selected offline for its reduced load count.
The B job's best-of-lane-A path is a sealed symbolic placeholder, resolved
from verified A receipts before launch; no fake seal or mutable job rewrite.
Plan mode checks all four possible B sandwiches without requiring GPU evidence.

Each screen is expected to take about 210 seconds. The inherited watchdog is
at least 840 seconds. Gaps are 90 seconds. Screen speed is diagnostic only.
The coordinator supplies fault review and device authorization. CPU preparation
never launches these jobs or changes the live queues.
