# Packet151 boundaries

No measured cost yet. Packet132 remains closed pending the upper-bound sibling cost measurement. Cost ≤ 1.952 ms reopens packet132 on packet114 independent text only; higher cost is inconclusive and requires full M=2. Never calibrate on the 12-prompt suite.

- Packet151d: never use direct `q.submit` or reference captures for a prepared
  sibling operation, and never enable sibling work for prefill (`fixture=0`).
  Miniature HOST_ONLY tests miss this device-branch error. Run the saved-rank,
  real-shape preparation regression as well as numerical gates.
  [Evidence and revisit conditions](PREPARATION-CLOSEOUT.md).

| Date | Attempt | Measured outcome | Revisit only when |
| --- | --- | --- | --- |
| 2026-10-19 | Reopen packet132 (confidence-gated two-candidate sibling half) by measuring the discarded second rank-0 row (alternate token `(token+1) % vocab`; partial M=2: dense/expert batched, HC/small tuples/shared-down/non-matrix serial) | One-load v5 `packet151e-sibling-bracket-B` (02:31–02:43 UTC), all views 13/13 exact, drift 0.06%: half A wall 16.10 → 34.07 ms (**+17.96 ms upper bound**), half A device 11.44 → 20.65 ms (**+9.21 ms**), interval 22.13 → 40.45 ms (instrumented build). The bar is ≤ 1.952 ms. The device extra alone is 4.7× the bar, so a full M=2 build would have to remove > 79% of even the device extra. **packet132 stays closed; no full-M=2 build.** | A design that avoids the second token's extra routed-expert and attention traffic (not just batching the serial M=1 submissions), with its own measured device cost ≤ 1.952 ms. |
