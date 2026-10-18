# Packet128b sampled in-engine budget — pending

No packet128b device run was launched by this CPU preparer. Its throughput,
overhead ratio, exact device output and class costs remain unmeasured.

The retained packet128 run measured **42.211168 tok/s**: **0.727779 × 58.0**
and **0.724034 × 58.3**, so its ranking remains withheld. The CPU regression
replays that old trace with post-hoc sampling and inferred queue routes; it
cannot establish this packet's overhead.

The coordinator runs the single proposed B job: twelve prompts × 64 tokens,
all tokens exact. Events are recorded for fixtures 9–16; the analyzer budgets
only complete paired cycles 10–16, all 48 layers and both outcomes. It runs
automatically after drain and lane release.

The first report line compares the measured rate against 58.0 and 58.3.
No ranking is constructed unless the rate reaches **52.2 tok/s** (0.90 × 58.0).
Compute/copy/other queue routes remain separate. Compute gaps exclude copy
clocks, missing IDs and sample boundaries; zero-duration copies are unresolved.
Any savings scenarios are optimistic sample projections, not measured gains.
