# Packet189 negative-result index (k3x: packet188's k3 + trims with the boundary export on the copy engine)

No device result exists yet. After the window, append the row from row 1's `bracket-summary.json` → `s189_decision` (or
`python3 -B v5/s189_decision.py <rows 0..1>`).

## Rulings (coordinator, 2026-10-22, quoted)

The k=3 ruling (packet188): "the V3 ruling on packet177 row 2 extends to a third boundary layer, on the same basis (the
per-layer costs are measured: rank-0 boundary 0.513 ms/layer, rank-1 saving 0.463 ms/layer), and the ledger row gets that
reasoning quoted. Build the composite you recommended."

The re-open ruling (packet189): "Packet188's loss is attributed to its own export path, not to the third boundary layer:
boundary_body rose 0.459 ms (the GDN layer-26 kernels, equal to the 0.463 ms saved on rank 1) while handoff_export rose
0.540 ms for the same 20,480 bytes because v3_boundary.hpp routed the export through kio_read_many (KioCopy, one work-item
per byte into pinned host memory, 28.9 ns/byte) instead of the copy-engine readback (2.6 ns/byte). The k=3 ruling stands;
packet189 re-measures k3 + trims with the export on the copy engine (k3x), and reads D from the draft's observed wall time."

## Rows checked before work (quoted; packet188's rows carried, plus the export-path search)

* **All 295 DO-NOT-REPEAT.md files under stage2** (lever-synthesis-3 corpus, `analysis/dnr-list.txt`) were grepped for
  `boundary_export`, `handoff_export`, "boundary export", "export path", "copy engine": no row closes a copy-engine export
  (it is V3's record path) or a GDN-only three-layer boundary with a verified token. The only k=3 closure is packet188's
  own measured row below, re-opened by the ruling above on the attribution it quotes.
* **packet188 boundaries** (all respected by k3x):
  * "Do not run layer 26 (or 24-25) inside a speculative half, or before the accept." k3x is the same boundary command.
  * "Do not add QSA layer 23 or 27 to the boundary." Not added (synthesis 3: 23-25 −0.66%, 24-27 illegal).
  * "Do not compare the bracket's V3 views with the record without row 1." Packet188's row 1 is the pinned fresh reference.
  * "Do not read the k3+trims vs V3 difference as k3 alone." The attribution is from the scopes: body +0.459 / export
    +0.540 / B −0.539 / A −0.142; the k3x price repairs only the export.
  * "Do not start a record chain below the chain rule." Kept: ≥ 1.02 × every V3 view AND ≥ 61.87271031814733.
* **packet177 row 2 (2026-10-19).** "Placement / depth / interleave for one sequence | Closed. ... | A new attribution
  showing rank0 slack ≥ 1 ms that is outside the draft dependency." Satisfied for k=3 by the ruling, as for V3: layer 26
  runs in the draft window for the verified token; under k3x the boundary (1.466) sits below the draft wall (1.537) on
  every packet188 hit (margin 0.072 mean).
* **packet177 row 3.** "Port the one-card wait / copy-engine fixes to two cards | Nothing to port. ... All copy stalls are
  < 0.1 ms/token (+0.6% if removed)." Consistent: kio-x on V3 alone prices +0.79%; it stays a component of the composite.
* **packet176 / packet171b.** "Packet176's B arm is a compute *kernel* path (stores/loads to USM host memory), not a copy
  command. Do not re-test it as a queue `memcpy` variant." and "Do not move one-card foreground copies onto the compute
  queue as `memcpy`". k3x does neither: the small kio transfers stay kernels; only the 20 KiB device→host export returns
  to the copy-engine readback the record already uses (the one large readback the ≤ 64 KiB rule let into the kernel path).
* **packet186 boundaries.** No speculative moved layers, no slim layout, no record chain below the rule, the smoke is not
  a speed result: all hold.
* **packet187 boundaries.** "Do not let KD's layer-streaming reference inherit V3 keys. Project `rank0_layers`, `boundary`
  and `snapshot_host` with the other target-only keys." The README's record-bundle recipe adds `kernel_io`,
  `rank0_prepare` and `boundary_export` to the projection. "Keep the bracket evidence map in the gate receipt. READY
  carries only its digest." Kept (`analysis-real-inputs.json`). "Do not treat the packet186 screen as a record." Kept.
* **packet185.** "Do not try a one-load switch of the head split: it is a storage choice." The bracket switches only
  `boundary`, `kernel_io`, `rank0_prepare` and `boundary_export` (execution keys); `rank0_layers`/`head` refuse in-load.
* **packet147 row 14, packet120, packet148, packet79, packet183, packet184** as in packet188's index: prepared inputs are
  admitted by packet186/187's measured gains; k=3 is not packet120 (after verification, outside the speculative half,
  head un-split); the placement change is explicit; the draft stays on rank 1; `dense_scales` stays `expanded`; the device
  rows never pass `--mini`.
* **Lever synthesis 2/3 rejected splits:** 23-25 (−0.06 to −0.66%; QSA in the island), 24-27 (QSA 27; illegal, −1.21% even
  if GDN), 25 only (−2.10%). k=2 (the record) and k=3 are the only viable splits.

## Measured (closed)

| Date | Arm | Outcome | Revisit only when |
| --- | --- | --- | --- |
| 2026-10-22 | **packet188: k3 + trims as built (the kio-export composite).** GDN layer 26 joins the verified-token boundary on rank 0 (`rank0_layers 0-26`, `boundary rank0-k3`; rank 1 from QSA 27) + `kernel_io=kernel` (both ranks, INCLUDING the 20,480-byte boundary export through the folded `kio_read_many` KioCopy readback) + `rank0_prepare=async`. Rows: k3+trims smoke, fresh V3 control (packet187 selection), one-load V3/k3+trims/V3/k3+trims/V3 (lane B, lanequeue-B35, 19:55-20:16 UTC) | **LOSS, closed as built.** Fresh V3 60.505; one load V3/k3+trims/V3/k3+trims/V3 = 60.526/60.564/60.536/60.382/60.540 (slower k3+trims view −0.26% vs the fastest V3 view; every view 13/13 exact, proposals and acceptance identical, V3 drift 0.058%). **Attribution (lever synthesis 3, coordinator ruling):** `boundary_body` +0.459 ms = the GDN layer-26 kernels (equal to the 0.463 ms saved on rank 1, below the priced 0.513); `handoff_export` +0.540 ms for the SAME 20,480 bytes = the export path (KioCopy per-byte readback into pinned host memory, 28.9 ns/byte, vs the copy engine's 2.6 ns/byte); D 1.61 → 0.43 was a model artifact (op-9 duration under the nonblocking draft; the draft wall was 1.586 → 1.537). Hits broke even (ready +0.398 from the 2.005 ms boundary vs race −0.461), misses +0.376 (the boundary is serial on the miss path). Trims real: 0.142 ms off rank 0's A. Evidence `packet188-twocard-k3-composite/v5/evidence/device-row2-bracket-v3k-k3trims-B-p188/bracket-summary.json` | A kio export path that is not per-byte (not planned: the copy engine already does it at 0.053 ms). Do not re-measure `boundary_export=kernel` for speed. |

## Measured (this packet)

| Date | Arm | Outcome | Revisit only when |
| --- | --- | --- | --- |
| 2026-10-22 | **k3x on the V3 record line:** packet188's k3 + trims with the boundary export back on the copy-engine readback (`boundary_export=copy`; `rank0_layers 0-26`, `boundary rank0-k3`, `kernel_io kernel`, `rank0_prepare async`). Rows: k3x smoke, one-load V3/k3x/V3/k3x/V3 (lane B); fresh reference = packet188 row 1 (60.50488520482965, pinned); decision `s189_decision` with D := draft wall; priced +2.74% (62.32 tok/s; pessimistic +2.27%, 62.04; optimistic +3.01) | **Measured 2026-10-22 (lane B, lanequeue-B36, 21:17-21:32 UTC): WIN, chain rule met.** One load V3/k3x/V3/k3x/V3 = 60.615/**62.242**/60.444/**62.225**/60.498, fresh V3 (packet188 row 1) 60.505; every view 13/13 exact, draft proposals and acceptance identical, V3 drift 0.28 %; slower k3x view +2.66 % over the fastest V3 view and ≥ 61.873. No kill rule fired: handoff_export 0.053 ms, boundary_total 1.481 ms, k3 hit saving 0.530 ms, Bd > draft wall on 0 % of hits, A trim 0.141 ms. Hit 14.062 → 13.531 ms, miss 25.770 → 25.569 ms; rank 1 binds 26 % of hits (was 100 %). Record bundle: packet190 (fresh chain on cards 0+1). Evidence `v5/evidence/device-row1-bracket-v3k-k3x-B-p189/bracket-summary.json` | — |

## Boundaries (do not)

* **Do not run layer 26 (or 24-25) inside a speculative half, or before the accept.** The moved layers' state is
  deliberately outside the image and the banks. The CPU negative control shows a guessed-token advance survives rollback.
* **Do not add QSA layer 23 or 27 to the boundary.** The island holds no QSA, KV, position or lookup operator, and both
  splits price as losses.
* **Do not route a device→host readback of more than a few hundred bytes through the KioCopy kernel.** It is one
  work-item per byte into uncached pinned host memory: 28.9 ns/byte measured on the 20,480-byte export (0.59 ms) against
  2.6 ns/byte on the copy engine. The `≤ 64 KiB` rule of `kio_sync` is the wrong bound for readbacks; the `boundary_export`
  key exists so the export is never silently re-routed.
* **Do not read the boundary-vs-draft rule from the op-9 duration.** Under `rank0_prepare=async` op 9 completes after the
  nonblocking host issue (0.43 ms); the draft's completion is `draft_rows.draft_wall_ms` (1.54 ms). `s189_decision` uses
  the draft wall; packet188's "Bd > D on 100% of hits" said nothing.
* **Do not compare the bracket's V3 views with the record without a fresh V3 load.** Packet188 row 1 (−0.05% vs the in-load
  views) is the pinned reference; if the storage or the V3 execution ever changes, run a fresh V3 row again.
* **Do not start a record chain below the chain rule**, and do not submit a screen. Only a fresh chain WS128 above
  60.659520, exact, is a record.
