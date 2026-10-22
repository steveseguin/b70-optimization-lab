# Packet188 negative-result index (two-card k3 composite on the V3 record line)

No device result exists yet, and this preparation closes nothing. After the window, append the row from row 2's
`bracket-summary.json` → `s188_decision` (or `python3 -B v5/s188_decision.py <rows 0..2>`).

## Ruling for k=3 (coordinator, 2026-10-22, quoted)

> "Ruling: the V3 ruling on packet177 row 2 extends to a third boundary layer, on the same basis (the per-layer costs are
> measured: rank-0 boundary 0.513 ms/layer, rank-1 saving 0.463 ms/layer), and the ledger row gets that reasoning quoted.
> Build the composite you recommended."

The reasoning behind the ruling has four parts:

* **The work is verified-token boundary work, not a speculative move.** Packet177 row 2 closes speculative placement
  "by the letter": rank-0 slack outside the draft dependency is 0.356 ms on V3, which is < 1 ms. k=3 does not use that
  slack. It runs layer 26 in rank 0's **draft window** (D 1.604 ms) for the verified token, as V3 does for 24-25:
  "V3 uses the draft window (D 1.6 ms) for verified-token work" (packet186 DNR).
* **Both per-layer costs are measured** on packet186's device rows: the rank-0 boundary costs 0.513 ms/layer and the
  rank-1 saving is 0.463 ms/layer.
* **The predicted boundary fits inside D.** It is about 1.54 ms, against D 1.604 ms, and exceeds D on 0.6% of hits. The
  bracket's kill rule checks this on device (> 5% of hits fires).
* **Layer 26 is GDN, as 24-25 are.** QSA layers are 23 and 27. So the island rule ("no QSA/position/lookup operator") holds.

## Rows checked before work (quoted)

* **packet177 row 2 (2026-10-19).**
  * The row: "Placement / depth / interleave for one sequence | Closed. The ceiling from rank0's 1.23 ms draft wait is
    +2.9%, and every measured move lost (p120, p127, p79, p71c). | A new attribution showing rank0 slack ≥ 1 ms that is
    outside the draft dependency."
  * Not met by its letter. It is satisfied for k=3 by the ruling above, on the same basis as V3.
* **packet177 row 3 (2026-10-19).**
  * The row: "Port the one-card wait / copy-engine fixes to two cards | Nothing to port. ... All copy stalls are < 0.1
    ms/token (+0.6% if removed). | Two-card fills or a BCS queue are introduced."
  * Kernel I/O is not adopted alone. Priced alone on V3 it is +0.57%, which agrees with the row. It is a component of
    the coordinator-ordered composite: under k=3 rank 0's A binds, so its round trips count (+0.39 points). It is
    separately selectable (`kernel_io`) so it can be attributed.
* **packet147 row 14.**
  * The row: "Exact input precomputation / prepared-buffer reuse / event-retirement batching ... p137 two-card projection
    +0.26–0.62% ... p137 stays closed-deferred until a separate measured ≥1.5% two-card gain."
  * The prerequisite is met: packet186 measured +3.31% and packet187 +3.17%. `rank0_prepare=async` is this row's
    prepared-input item, applied only to rank 0's speculative half.
* **packet176 / packet171b.**
  * The rows: "Packet176's B arm is a compute *kernel* path (stores/loads to USM host memory), not a copy command. Do not
    re-test it as a queue `memcpy` variant." and "Do not move one-card foreground copies onto the compute queue as
    `memcpy` (packet171b, +0.40% neutral)".
  * `p188::KioCopy` is a compute kernel through pinned host staging (one work-item per byte), not a queue memcpy.
* **packet186 boundaries.**
  * The boundaries:
    * "Do not run the moved layers inside a speculative half, or before the accept."
    * "Do not add a slim layout to this packet's bracket."
    * "Do not start a record chain from a screen winner below the chain rule."
  * Layer 26 runs only in the boundary command, after the accept; `v3_check_plan` enforces this over the stored set.
  * There is no slim layout: rank 1 keeps 24-47, and the census delta on rank 1 is 0.
  * The chain rule here is +2% over every V3 view AND ≥ 61.873.
* **packet186 pending row (measured 2026-10-22).**
  * The row: "WIN, chain rule met. ... Rank-1 saving 0.463 ms per moved layer, boundary 1.026 ms, hit cycle 14.78 ->
    14.06 ms, rank 1 binds 100% of hits".
  * These are the measured s1/c0 inputs of the k=3 price.
* **packet185 boundary.**
  * The row: "Do not try a one-load switch of the head split: it is a storage choice."
  * The bracket switches only `boundary`, `kernel_io` and `rank0_prepare`. `rank0_layers` is a storage choice and is
    refused in-load, so the fresh V3 control (row 1) is a separate load.
* **packet187 boundaries.**
  * The rows:
    * "Do not let KD's layer-streaming reference inherit V3 keys. ... Project `rank0_layers`, `boundary` and
      `snapshot_host` with the other target-only keys."
    * "Keep the bracket evidence map in the gate receipt. READY carries only its digest."
    * "Do not treat the packet186 screen as a record."
  * The README's record-bundle recipe adds `kernel_io`/`rank0_prepare` to the KD projection.
  * The analysis inputs map lives in `v5/evidence/analysis-real-inputs.json`, and `analysis.json` carries its digest.
  * The packet188 screen is never a record.
* **packet120 result note.**
  * The note: "Moving one target layer to rank 0 adds ~0.59 ms to hits and ~1.0 ms to misses ... Closed."
  * k=3 is not packet120. It runs after verification, outside the speculative half, with the head un-split.
* **packet148.**
  * The row: "Do not silently change static hit placement or revive packet120/123."
  * The placement change is explicit (selection keys) and recorded here.
* **packet79.** The draft stays on rank 1.
* **packet183.** "S1 ... Closed: loss -6.2%." `dense_scales` stays `expanded`, and the domain refuses `metadata`.
* **packet184 mistakes row (2026-10-22).**
  * The row: "v5 bundle-8 binaries refuse `--mini` ... build the probe only at production geometry."
  * The device rows never pass `--mini` (`argument_gate`). The five-layer miniature is only for the gnu-host CPU twin
    (`--pipeline-mini5`).
* **Lever synthesis 2 rejected splits** (`analysis/lever-synthesis-2-20261022.md`): 23-25 (−0.06 to −0.52%; QSA in the
  island), 24-27 (QSA 27; −1.21% even if GDN) and 25 only (−2.10%). k=2 (the record) and k=3 are the only viable splits.

## Pending

| Date | Arm | Outcome | Revisit only when |
| --- | --- | --- | --- |
| 2026-10-22 | k3 + trims on the V3 record line: GDN layer 26 joins the verified-token boundary on rank 0 (`rank0_layers 0-26`, `boundary rank0-k3`; rank 1 from QSA 27) + `kernel_io=kernel` (both ranks) + `rank0_prepare=async` (rank 0 A). Rows: k3+trims smoke, fresh V3 control (packet187 selection), one-load V3/k3+trims/V3/k3+trims/V3 (lane B); decision `s188_decision`; priced +1.49% (k3), +1.88% (+kernel I/O), +2.39% (+prepare off A); chain needs ≥ 0.105 ms off A on top of k3 | **Pending (CPU-prepared, READY 2026-10-22).** Kill rules: k3 hit saving < 0.25 ms; Bd > D on > 5% of hits; trims remove < 0.105 ms of A | — |

## Boundaries (do not)

* **Do not run layer 26 (or 24-25) inside a speculative half, or before the accept.** The moved layers' state is
  deliberately outside the image and the banks. The CPU negative control shows a guessed-token advance survives rollback.
* **Do not add QSA layer 23 or 27 to the boundary.** The island holds no QSA, KV, position or lookup operator, and both
  splits price as losses.
* **Do not compare the bracket's V3 views with the record without row 1.** They load the k3 storage, with +1.13 GB and
  layer 26 idle on rank 0. The fresh V3 load and the drift bound tie them to the record line.
* **Do not read the k3+trims vs V3 difference as k3 alone.** The trims are attributed from rank 0's A (layers 0-23 are
  identical in both views) and from the envelope scopes. If the split matters, run a `k3`/`k3kio`/`k3prep`/`k3trims`
  one-load attribution (the selections exist).
* **Do not start a record chain below the chain rule**, and do not submit a screen. Only a fresh chain WS128 above
  60.659520, exact, is a record.
