# Packet168 qualification boundaries

This preparation is incomplete; it does not close the requested census or an
optimization lever.

* Do not relabel isolated target-half replay as a native emission interval.
* Do not count an unimplemented transfer mask as a measured zero cost.
* The local head is not the complete split head/argmax/merge path.
* Route/shared activation and shared-down/mixture are fused on bundle8. A label
  partition is not a disjoint kernel-cost partition.
* A marker-only CPU backend does not test snapshot copies. Preserve the first
  unsupported-compute failure and the real-copy poison/restore fixture.
* A successful old CPU binary does not qualify a failed new fixture build.
  `cpu-builder-status.json` binds the current fixture and binary before execution.
* Parent token streams validate parsing/exactness; they contain no packet168
  class differences. Never fill the missing ranked table from old synthetic
  prices, sampled intrusive timers or assumed transfer percentages.
* Queue plan and report-adapter passes do not override false native readiness.

## packet168b additions

* Do not make a changed expert route a hard refusal inside a skip arm. Any
  upstream skip legitimately changes router inputs, so the old
  `require(same_routes)` would have stopped the device run at the first arm.
  The marker-only CPU fixture could not detect this. Record
  `route_identity_preserved` instead. The expert count and shapes stay fixed.
* Do not read the residual as transfer cost. It is subtraction-only and also
  holds the split head, controller/mailbox time, overlap and any
  passes-per-token difference.
* Do not split the fused router/shared-expert launches into two classes.
* The device worker imports `fault_review.py`, which needs
  `lineage/window_driver.py`. Any new screen that imports it must carry that
  file (the report adapter caught this).
* Rank 1's census image (`--census-probe`) costs measured device bytes. The
  parent memory plan would refuse rank 1 at startup unless
  `memory-plan-census.json` adds them.

## packet168 v3 additions (after device-census-B-v2)

* Do not run a diagnostic body pass at a position the engine has not admitted.
  The setup request admits only its last half-step position P-1, but `commit`
  leaves the device position at P. When P is a multiple of 32 the prepared
  `qsa_select`/`qsa_attention` launch extent equals P, and the device guard
  `pos > position_limit(s) - s.tokens` sets the sticky error. In v2 this hit
  the **control** pass at benchmark-analysis (65 + 63 = 128), so it was not an
  attention-arm effect, and dropping an arm cannot fix it. `probe()` now calls
  `admit_position(P)` before the image and signature, and mirrors the guard on
  the host.
* Do not trust a CPU fixture that probes at positions 0..11. Fixture positions
  must be the real probe positions (prompt tokens + 63).
* Attention has no arm since v3 (packet173 finds no attention lever). Its
  `qsa_*` launches run in every pass and are part of the residual.
