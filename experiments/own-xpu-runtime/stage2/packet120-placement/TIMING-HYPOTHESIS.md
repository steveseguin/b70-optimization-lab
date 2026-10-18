# Why the screen must measure misses

Packet108's source budget predates the combined packet118 bundle. Its figures
are useful for reasoning about dependencies, not as packet120 measurements.
The bracket's control is the exact packet118 bundle7 selection, not packet108's
older source line. No projected number below is a benchmark or promotion claim.

Using the conditional means in packet108 `budget.json`, hit race slack is
0.518055 ms and miss race slack 0.790943 ms. For a hypothetical layer of cost
`d` moved unchanged from rank1 to rank0, leaving all other work and offsets
unchanged:

- Hit duration change: `max(-d, d - 0.518055)` ms.
- Miss duration change: `d + max(-d, d - 0.790943)` ms, because the corrected
  rank0 half also gains the layer.

At d=0.50 ms this is about **−0.018 ms per hit, +0.209 ms per miss**. At
0.55 ms it is **+0.032 ms per hit, +0.309 ms per miss**. The roughly 1.78 ms
draft wait is not extra target-race slack. These are conditional illustrative
calculations from an older configuration; real costs, head splitting and the
new prefix can change the balance. They do not justify the brief's approximate
+3% prediction, nor do they justify a speed verdict without the requested
fresh-process bracket. A half-layer move would be a different experiment.

Use all twelve prompts, exactly matching target outputs and draft acceptance,
and report both the ordinary primary class-balanced rate and the first99
hit/miss and per-rank command means. A controls-only fresh-process bracket is
required on each lane; no isolated fast process can select this candidate.
