# Packet58ac do-not-repeat

| Date / arm | Outcome and retained evidence | Revisit condition |
| --- | --- | --- |
| 2026-10-18 / exact changed-entry cache publication on 58z one-card tile16, overlap, 21.553 GB cache | No-build under the ≥60% net-removal gate. Packing costs 0.053–0.060 ms against a required 0.738753 ms saving. 480 CPU transactions pass under each compiler, but current-identity transfer/scatter/fixed-wait split is unknown. [Analysis and closeout](ANALYSIS.md), [measurements](analysis.json). | Current-identity evidence supports a complete safe boundary ≤0.492502 ms/token after new overhead and fill-cadence costs, then unchanged `iq3-p49-split32-v1` device/oracle/determinism gates. |

- Do not claim 58v's already-adopted 144-upload-to-one change again.
- Do not equate >99% fewer table bytes with ≥60% less boundary time.
- Do not call CPU memcpy/scatter timings device measurements.
- Do not call 58y's wait scopes pure synchronization or transplant its 18 GB
  instrumented timing directly onto 58z's 21.553 GB record.
- Do not publish during a live position, overwrite before revocation completes,
  restore old victims after failed fills, or use generation counters as a
  substitute for a reader fence. Device resolution does not validate generation.
- Include victim and fill IDs, generation-only updates and final-plan values;
  deduplicate before apply. `Plan::epoch` alone is not a unique overlap ticket.
- A 64-ID sensitivity is not a measured dirty-set count or capacity limit.
- Existing packet trees, screen/ops trees and live queues remain frozen.
