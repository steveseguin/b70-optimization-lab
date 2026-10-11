# Packet 26: do not repeat

| Closed arm | Evidence | Revisit condition |
| --- | --- | --- |
| generic descriptor-interpreting kernel | [Packet 24 card measurements](../packet24-kernels/evidence/20261011-k2-c0-generic-kernels-slow/README.md): 50–100× regressions for several classes | Do not restore Batch/Chain. A dedicated compiled class must pass exactness and same-card K2 first. |
| launch count used as a speed metric | [Packet 20 launch receipts](../packet20-launch/receipts-card3-20261011-attempt-a/README.md); a launch measured 3.4–5 microseconds | Count launches for accounting only. Measure GPU events and whole-token wall time. |
| kernel parameters behind a pointer in the hot loop | Packet 23/24 parameter indirection accompanies generic slow kernels | Capture bounded parameters by value; a needed table is loaded into local values once per work-item. |
| optimisation adopted without a per-class timing on the card | [K2 admission](WINDOW.md) | Default packet18. Admit only exact candidates below 0.9× the reference median execution sum. |
| changing cross-card event fences while reducing host overhead | [Packet 18 isolation review](../packet18-decode-v2/review-queue-isolation.md) | Preserve the host drains and foreign-event rejection. No cross-card event chain. |
| pretending CPU mock time is native submission time | [Host issue benchmark](host-issue-benchmark.json) | W2 enqueue_loop_ms is the required device-window evidence. |
| precision flags only at compile time | [Packet 17 link incident](../packet17-detmath/evidence/20261011-wb-a-link-flags/README.md) | Check every compile and link command. |
