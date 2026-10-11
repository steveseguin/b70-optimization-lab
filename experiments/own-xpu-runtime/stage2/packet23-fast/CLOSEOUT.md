# Packet 23 CPU preparation closeout

Question: can the qualified fused v2 schedule shed timing and host submission
cost without changing arithmetic or launch order? Identity: packet21 fused
schedule, v2 deterministic arithmetic, frozen or R5 GEMV, 16-bit model state.

Implementation removes profiling from token/drain queues, timing-only pending
records, quadratic owner ledger growth and linear arena searches. Completion
of the chained tail proves the segment complete; native synchronize and all
ownership/queue checks remain. Resident non-GEMV bindings are memoized.
Canary borrower lifetime fixes and closed environment admission are preserved.

Evidence: [build receipt](build-receipt.json), [CPU gates](cpu-tests.json),
[submission benchmark](submission-benchmark.json), [streaming check](streaming-real.json),
[carryover proof](carryover-proof.json), and [exact host diff](host-plumbing.patch).
The original long real-model and sanitizer receipts retain their original
binary identities. They are not new packet23 executions.

No device ran in this task. Device correctness, fused kernel duration and
speed remain open until the coordinator completes K1/W0/W2/W3. The fixed
876-launch schedule can still be slower due to fused-kernel occupancy and
recomputed transforms; launch reduction is no throughput claim. Next action:
run the separately gated windows in WINDOW.md; preserve all failures and
receipts. This closes CPU preparation only, not the optimization lane.
