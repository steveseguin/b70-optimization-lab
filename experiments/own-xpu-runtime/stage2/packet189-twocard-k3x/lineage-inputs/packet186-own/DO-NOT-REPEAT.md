# Packet186 negative-result index (two-card V3: verified-boundary rebalance)

No device result exists yet, and this preparation closes nothing. After the window, append the row from row 3's
`bracket-summary.json` -> `s186_decision` (or `python3 -B v5/s186_decision.py <rows 0..3>`).

## Rows checked before work (quoted)

* **packet185 DO-NOT-REPEAT, pending row, measured 2026-10-22:**
  * The row: "V3 GO. Split 58.601/58.536/58.621, full head 57.737/57.756 tok/s (-1.5%) ... u = 0.222 ms ...
    decoupled B-A = 0.851 ms, sigma = 0.403 ms/cycle ... Un-split ALONE is a loss and stays closed; V3 ... is open
    and built as packet186."
  * How packet186 honours it: the un-split head appears only as V3's placement and as the in-load U control, never
    as a candidate.
* **packet185 boundary:** "Do not try a one-load switch of the head split: it is a storage choice."
  * Respected. The bracket loads one storage, the V3 dual layout with the full head on rank 1, and switches only
    `boundary`/`snapshot_host`.
  * The split-head controls are fresh loads (rows 1 and 3). The native bracket refuses `head`, `rank0_layers` and
    `dense_scales: metadata` switches (`full-shape.json`, 19 refusals per dual run).
* **packet185 boundary:** "Do not count this packet as V3 evidence beyond u and B − A: ... s1, c0, accept ordering
  are not measured here."
  * The pricing keeps s1 and c0 as stated inputs with the coordinator's corners. c0 is anchored on the measured
    rank-0 layer_body: 0.483 ms per layer.
  * The bracket measures s1 directly: `measured.s1_rank1_saving_per_moved_layer_ms`.
* **packet177 row 2:** "Placement / depth / interleave for one sequence | Closed ... | A new attribution showing rank0
  slack ≥ 1 ms that is outside the draft dependency."
  * The coordinator's ruling after packet185's V3 GO is to build V3.
  * V3 uses the draft window (D 1.6 ms) for verified-token work and leaves the 0.852 ms/hit slack outside the draft
    dependency untouched.
* **packet120 result note:** "Moving one target layer to rank 0 adds ~0.59 ms to hits and ~1.0 ms to misses ...
  Closed."
  * V3 is not packet120. Its layers run after verification, outside the speculative half A, with the head un-split
    (packet120 coupled through sigma).
  * Packet120's 0.59 ms/layer is kept as a pessimistic c0 input (0.55-0.73).
* **packet148:** "Do not silently change static hit placement or revive packet120/123." The placement change is
  explicit (selection keys), and no partial layer is put in A's tail.
* **packet160 / packet156 / packet123:** V3 serves no B work during B and exchanges nothing per layer. It does not
  count rank 1's suffix idle time or bundle 7's command tail as slack.
* **packet153 result note (2026-10-19):** "static descriptors could join a future composite bundle ... They are not
  adopted alone."
  * They are bundled here, not adopted alone. Under V3 rank 0's A binds the emission (central +0.17 %, up to +0.9 %).
* **packet183:** "S1 ... Closed: loss -6.2%." `dense_scales` is fixed to `expanded`, and the bracket domain refuses
  `metadata`.
* **packet79:** the draft stays on rank 1.
* **packet184 mistakes row (2026-10-22):** "v5 bundle-8 binaries refuse `--mini` ... build the probe only at
  production geometry."
  * Done the same way. The p149 probe is built only when not mini; it stays inert under `probe: off`, and production
    allocation order is unchanged (bundle-8 capture identity with packet185).

## Pending

| Date | Arm | Outcome | Revisit only when |
| --- | --- | --- | --- |
| 2026-10-22 | V3: full target head on rank 1 + GDN layers 24-25 on rank 0 for the verified token (boundary command after every rank-0 accept, rank 1 from layer 26), bundled with packet153 static snapshot; rows: V3 smoke, fresh bundle-8 control, one-load U/V3/U/V3/U, fresh bundle-8 control (lane B); decision `s186_decision` | **Measured 2026-10-22 (lane B, lanequeue-B34, 16:09-16:34 UTC): WIN, chain rule met.** One-load U/V3/U/V3/U 57.832/60.573/57.802/60.533/57.840, fresh split-head controls 58.595/58.441; every view 13/13 exact, draft proposals and acceptance identical, drift 0.26%; +3.31% over every control, both V3 views >= 59.974. Rank-1 saving 0.463 ms per moved layer, boundary 1.026 ms, hit cycle 14.78 -> 14.06 ms, rank 1 binds 100% of hits (`v5/evidence/device-row3-control-production-B-p186/bracket-summary.json`, `s186_decision`). Record bundle = packet187 | — |

## Boundaries (do not)

* **Do not run the moved layers inside a speculative half, or before the accept.** Their state is deliberately
  outside the image and the banks. The CPU negative control shows a guessed-token advance survives rollback.
* **Do not add a slim layout to this packet's bracket.** Rank 1 dropping its idle 24-25 copies is a load-time storage
  change. It needs its own fresh loads and has no speed effect.
* **Do not read the smoke row as a speed result.** It has 64-token views. Do not compare the bracket's V3 views with
  the fresh-load controls without the drift bounds.
* **Do not start a record chain from a screen winner below the chain rule.** The rule is +2 % over the faster
  split-head control AND 59.974 tok/s.
