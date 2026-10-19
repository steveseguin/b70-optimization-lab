# Packet177 decision index

| Date | Mechanism | Outcome | Revisit only when |
|---|---|---|---|
| 2026-10-19 | Re-price exact intra-layer TP (p45 layout) on bundle 8 | Closed on CPU. Halved compute is 16.10 ms with the replicated HC/router/shared work 7.38 ms. Break-even is 6.62 µs per phase with zero split overhead. Even the 3.3 µs packet12 device-copy floor gives only +2.9%, or −5.3% with assumed split costs. At the measured 18.6 µs it is −15.6%. See [PLAN](PLAN.md) §4a and [options.json](options.json). | A measured cross-card dependency of ≤ 3 µs per phase **and** an exact placement that removes the replicated HC/router/shared work without adding equal cuts. |
| 2026-10-19 | Placement / depth / interleave for one sequence | Closed. The ceiling from rank0's 1.23 ms draft wait is +2.9%, and every measured move lost (p120, p127, p79, p71c). | A new attribution showing rank0 slack ≥ 1 ms that is outside the draft dependency. |
| 2026-10-19 | Port the one-card wait / copy-engine fixes to two cards | Nothing to port. Waits are already pure spin, there are no fills, and every copy is on the in-order CCS queue. All copy stalls are < 0.1 ms/token (+0.6% if removed). | Two-card fills or a BCS queue are introduced. |
| 2026-10-19 | Count a two-sequence aggregate as the single-user record | Forbidden. LocalMaxxing withholds aggregate `tokSOut`; it is a neural.download concurrency profile only. | The owner defines an aggregate record class. |
