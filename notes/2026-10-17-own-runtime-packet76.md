# Packet 76 — rank 1 host scheduling

Attribution completed on CPU from saved receipts. Of packet69's 1.608 ms
residual, 1.457 ms is host housekeeping outside its preparation, issue and wait
timers; 0.092 ms is outer setup; 0.001 ms is the observed device gap after the
last layer; 0.057 ms remains unresolved. The matched control has only 0.666 ms
in the housekeeping bucket. Observation overhead accounts for much of the
original residual. This is not a measured 1.608 ms opportunity.

The saved trace lacks per-submit timestamps, complete layer coverage and useful
copy timestamps. It cannot prove a complete causal split. The rank0 handover and
mailbox arrival precede the measured half. [Attribution and limits](../experiments/own-xpu-runtime/stage2/packet76-rank1-host/ATTRIBUTION.md),
[calculations and input hashes](../experiments/own-xpu-runtime/stage2/packet76-rank1-host/ATTRIBUTION.json).

Next: copy packet70 sources, retain its kernels and selected wide64/draft-HC/
batch-copy setup, and screen ordered-queue event retirement on rank1. The old
path polls every completed event again. Add host retirement/profiling timers;
the old receipts do not isolate their individual cost. Device correctness and
speed remain pending. Shared pinned v4 screens and temporary queue planning
will prepare the coordinator's A grid and B winner check.

No GPU, model, service, sudo or host-setting change. The initial pull was
blocked by a pre-existing dirty orchestration log; fetch proved local main
equal to origin/main. That log and all frozen paths were left untouched.
