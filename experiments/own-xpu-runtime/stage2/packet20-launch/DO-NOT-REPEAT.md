# Packet20 do not repeat

| Closed mistake | Retained evidence / rule | Revisit condition |
| --- | --- | --- |
| a watchdog set to the expected run time | Incident 5 (2026-10-11 02:34 UTC): a stop during startup/JIT can fault the engine. The 30/50 s watchdogs are withdrawn; expectations only report. [Deadline audit](../packet18-decode-v2/DEADLINES.md). | Never restore a short total-time cutoff; keep first-use JIT and at least 4× margin in every signal deadline. |
| Calling compilation a B70 runtime pass | All native methods are unrun; decision table says not measured | A separately admitted complete device window |
| Concatenating phases across work-groups with only a local barrier | Fusion prototype uses one group for a whole chain; fusion plan explains performance tradeoff | A dependency-correct parallel schedule with exact gates |
| Changing the reduction tree when padding attention | REPLAY preserves active-prefix tree and original missing-partner add-zero | Never under v2 identity |
| Ranking logits instead of rounded normalized probabilities | Route ranks exact v2 probabilities with original ID tie order | Never under v2 identity |
| Destroying graph/queue/USM during exception unwinding | Native failure retains ownership; watcher leaves a failed drain parked | Only a completed drain allows teardown |
| Capturing temporary host-pointer copies or host readback | Token-state H2D outside capture; source owned through completion | No host-pointer capture in this design |
| Treating repeated constant output as replay liveness | Alternating token state, reset input and full exact expected-output check | Changed-input gate must remain |
| Assuming append order or SYCL wait covers a raw queue | Native in-order flags and explicit native completion/sync | A separately verified explicit dependency implementation |
| Omitting link precision flags | Builders assert final link.txt and compile flags | Never |
| Counting packet3 sites as packet18 launches | DAG normalizes grouped expert gate/up and two-pass MoE combine; count physical split GEMVs | Regenerate counts for a changed dispatch identity |
| Omitting partial fusion tail at N=100 | ceil(N/8)=13; last launch does four operations | Never compare unequal work |
| Quoting device timestamp envelope as pure kernel time | Per-row timing definitions distinguish envelope and profiled span | Retain matched definitions |
| Claiming opaque driver allocations fit the explicit arena census | 87,040 explicit device bytes; opaque allocations unmeasured | A device memory-accounting gate |
| Repeating a failed device window | Persistent latch, one child, no automatic retry | Coordinator recovery and fresh admission |

[CPU preparation closeout](CLOSEOUT.md). The issuing overhead question remains
open until measured; this file closes mistakes, not the optimization lane.
