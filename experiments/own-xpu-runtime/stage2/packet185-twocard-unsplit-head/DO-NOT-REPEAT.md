# Packet185 negative-result index (two-card un-split target head: measured attribution)

No device result exists yet; this preparation closes nothing. After the window, append the row from view row 4's
`bracket-summary.json` -> `s185_decision` (or `python3 -B v5/s185_decision.py <five outputs>`), and append its
`attribution` text to packet177's placement row whatever the outcome.

## Rows checked before work (quoted)

* **packet177 DO-NOT-REPEAT, row 2 (the row this packet answers):** "Placement / depth / interleave for one sequence |
  Closed. The ceiling from rank0's 1.23 ms draft wait is +2.9%, and every measured move lost (p120, p127, p79, p71c). |
  A new attribution showing rank0 slack ≥ 1 ms that is outside the draft dependency." Coordinator ruling 2026-10-22:
  it stays closed by its letter until the attribution is MEASURED. Packet185 measures it; it builds no V3.
* **packet177 row 3:** "Port the one-card wait / copy-engine fixes to two cards | Nothing to port ... All copy stalls are
  < 0.1 ms/token (+0.6% if removed). | Two-card fills or a BCS queue are introduced." Not touched here.
* **packet120 result note (2026-10-18):** "Moving one target layer to rank 0 adds ~0.59 ms to hits and ~1.0 ms to misses
  ... Closed." Not repeated: no layer moves here.
* **packet127 note:** "rank-1 → rank-0 work moves are closed until the in-engine attribution (packet 128) shows otherwise."
  Packet185 moves the 46,080 suffix rows the other way (back to rank 1) and only to measure.
* **packet128b finding:** "Rank 1 `wait.head.suffix` 1.62 / 1.23 ... rank 0 computes (0.29 ms) only after its own speculative
  half (packet 105b design). This explains why the head split realised only +0.37% ... and why moving more rows/layers to
  rank 0 lost (packets 127, 120)." Packet185's split views measure that service directly (`sigma_rank0_service_ms`).
* **packet130 note:** suffix interleave "−1.61%, closed". Not repeated: no interleave.
* **packet148:** "correction-only moving layer boundary | ... Do not silently change static hit placement or revive
  packet120/123." No placement change here.
* **packet106b grid (2026-10-18, bundle-6 era):** "Head split: +0.36% over the better control". The only retained
  un-split-vs-split device evidence; v4 fresh-load arms (decision-fixtures/packet106b-v4): un-split B − A 0.524 ms, split
  B − A 0.480 ms (coupled), B difference +0.049 ms (lower bound of u on that line).
* **packet183 (2026-10-22):** "S1 metadata scales ... Closed: loss -6.2%". Packet185 reuses packet183's engine with
  `dense_scales: expanded` only (its controls 58.617/58.587/58.630 = bundle 8); no S1 view.
* **packet160 / packet156 / packet79 / packet123:** no draft move, no suffix-slack use, no partial layer.

## Pending

| Date | Arm | Outcome | Revisit only when |
| --- | --- | --- | --- |
| 2026-10-22 | Un-split target head (target_head=production, full 248,320-row head on rank 1, no rank-0 suffix service) vs bundle 8 split head; five fresh loads C/U/C/U/C on lane B; decision `s185_decision` | **PENDING (CPU-prepared, not queued).** Rule: V3 GO iff u ≤ 0.39 ms AND decoupled B − A ≥ 0.60 ms AND every view 13/13 exact with identical draft proposals AND control drift ≤ 3%; else V3 closed and packet177(b) keeps its closure with this attribution appended. | — |

## Boundaries (do not)

* Do not try a one-load switch of the head split: it is a storage choice (rank 1 loads 202,240 vs 248,320 rows, rank 0
  the suffix or nothing; census delta −157,322,272 / +155,750,384 B) and the native bracket refuses it in both directions
  (`v5/evidence/full-shape.json`, 15 refusals per run). A one-load design needs a new binary; this packet reuses packet183's.
* Do not read the un-split rates as a speed result or compare fresh-load rates across views: the decision quantities are
  the per-view interval components (A, B, D) of the packet85 model; rates enter only through the 3% control drift bound.
* Do not use the split views' B − A as the decoupled number: on bundle 8 the split arm sits 0.126 ms above the A + σ floor
  (packet183 controls today: B − A 0.652/0.668/0.652 ms, σ service 0.402–0.405 ms/cycle).
* Do not treat `u` as resolved when |u − 0.39| is within the control hit-B spread or the draft-corrected u lands on the
  other side of 0.39 (`u_resolved` in the decision); repeat the five rows rather than widen the threshold.
* Do not count this packet as V3 evidence beyond u and B − A: V3's other inputs (rank-1 saving per moved layer s1, rank-0
  cost per layer c0, accept ordering) are not measured here.
