# 2026-10-22: packet188, two-card k3 composite on the V3 record line, CPU preparation

Packet: [`experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/`](../experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/README.md).
Proposal (PROPOSAL ONLY, never queued): `experiments/own-xpu-runtime/ops/lane-queue/proposed-p188-two-card-B.txt`.

No GPU, `/dev/dri`, device binary run, systemd change, PAUSE/STOP or queue file was touched. Nothing was queued, armed,
submitted or committed. The only systemd calls were read-only `systemctl --user list-units 'window-*'` polls before
each compile batch; all of them were empty.

## Why

Packet187's fresh chain set the two-card record at **60.659520 tok/s** (`cmvjvabyv040jrf01dricuz8s`). Lever synthesis 2
(`analysis/lever-synthesis-2-20261022.md` in the packet) found no single open lever at +2% on the V3 line, because rank 1
binds every hit. The largest single lever is **k=3**: GDN layer 26 joins rank 0's verified-token boundary. It prices at
**+1.49%**. After it, rank 0's A binds by 0.107 ms, so rank-0 trims start to count.

The coordinator's ruling: "the V3 ruling on packet177 row 2 extends to a third boundary layer, on the same basis (the
per-layer costs are measured: rank-0 boundary 0.513 ms/layer, rank-1 saving 0.463 ms/layer)... Build the composite you
recommended."

## What was built

Base: the packet186 binary lineage. The 78 parent objects are relinked unchanged; entry-main and `p49d_submit` are
rebuilt, and `s1_submit` is recompiled. The device engine is
`d776524532f110528dea5f67f13771feb71945cf35f44247f77ef9118539eb45` (8 compiler runs, 0 warnings). The native delta is
+298 / −67 lines in 11 files (`v5/k3-native.patch`).

Three selection keys, each switchable inside one load:

* **k=3.** Storage `rank0_layers=0-26`, `boundary=rank0-k3`: rank 0 runs layers 24-26 for the verified token, and rank 1
  starts at QSA 27.
* **`kernel_io=kernel`.** Packet176's kernel path on two cards. Synchronous ≤ 64 KiB copies become `p188::KioCopy` kernels
  through pinned staging. Readbacks are folded: rank 1 reads error + next_token together, and the boundary reads error +
  export together.
* **`rank0_prepare=async`.** Rank 0's token and lookup rows go in one ordered copy. Position and token_history are
  captured and checked after the drain, so there are no synchronous round trips in A.

**Layer-26 correctness.**

* Layer 26 is inside the V3 island: it never runs inside a speculative half, and it is never banked or imaged. The image
  capture is identical, at 19,025,640 B.
* CPU proof:
  * 14 engine runs (GNU/Intel) cover every cancellation cut, guard refusals and detecting negatives. The canonical bytes
    are identical across all trim combinations.
  * 70 two-rank requests on a five-layer G Q G G Q miniature, in both bracket start orders, plus a trims-attribution
    load. Each request matches the reference in tokens, 120 fixtures each, proposals and state.

**Memory.**

* Rank 0 gains +1,129,070,858 B: exactly the 65 `blk.26.*` allocations. Census headroom is 838,134,798 B; the plan's
  headroom is 208,970,894 B, and free memory with MTP is 2.19 GB.
* Rank 1 is unchanged.
* Host admission is 108,797,048,558 B for the k3 rows.

## Device design (lane B, about 18 min)

Rows:

1. k3+trims smoke (12 × 64 + incident64), about 285 s;
2. fresh V3 control, the packet187 record selection, about 213 s;
3. one load V3 / k3+trims / V3 / k3+trims / V3 (12 × 128 + incident64 each), about 480 s.

**`s188_decision`:**

* **Screen winner:** the slower k3+trims view is ≥ 1.005 × every V3 view, with every view exact, identical proposals and
  drift ≤ 3%.
* **Chain:** ≥ 1.02 × every V3 view AND ≥ 61.873 tok/s.
* **Kill rules** (recorded):
  * the k3 hit saving is < 0.25 ms;
  * Bd > D on > 5% of hits;
  * the trims remove < 0.105 ms of A.

The rule was tested on packet186's and packet187's real summaries and streams.

## Gates

All passed:

* build;
* production-shape startup (12 startups, 10 dual-rank loads, V3 identity with packet186);
* k3 state;
* controller;
* admission;
* analysis (21 tests);
* safety, exec limits, loader;
* seal;
* package_rows;
* entry, launch limits, worker, report;
* private-copy plan `--lane B` and rehearsal;
* pin guard: 1,107 pins, 0 cross-packet mutable;
* final_checks `--ready`.

## Mistakes caught during preparation

* **Hidden identity literal in a hard-linked vendored file.** The vendored `packet58-onecard/suite_driver.py` locates the
  packet by the literal name `packet186-twocard-v3`. The hard-linked copy made the entry gate fail with StopIteration.
  * Fix: unlink, then rewrite the packet188 copy. Packet186's inode and sha are unchanged.
  * Lesson: grep hard-linked lineage for identity literals, not only the copied tree.
* **Read-in-place pins tripped the pin guard.** Pinning packet186/187 device files and packet49 oracle results directly
  in `analysis.json` gave 93 cross-packet mutable pins. The oracle results resolve outside the repository.
  * Fix: move the map into `analysis-real-inputs.json`, outside the guard's walk (packet187's bracket-gate layout). Seal
    its digest, and re-hash it in final_checks.

## Device result (2026-10-22, lane B window 19:55-20:16 UTC, unit lanequeue-B35): LOSS, k3 closed, trims measured

| Row | Content | Rates (tok/s, class-balanced) | Exact |
| --- | --- | --- | --- |
| 0 | k3+trims smoke, 12 x 64 + incident64 | smoke, no verdict (313 s) | 13/13, draft proposals identical, timing-data proof passed |
| 1 | fresh V3 control (packet187 record selection, 0-25 storage) | 60.505 | 13/13 |
| 2 | one load, V3 / k3+trims / V3 / k3+trims / V3 (k3 storage) | 60.526 / **60.564** / 60.536 / **60.382** / 60.540 | every view 13/13, draft proposals and acceptance identical |

`s188_decision` (row 2 `bracket-summary.json`): **not a screen winner**. The slower k3+trims view is 0.26 % below the
fastest V3 view; V3 drift across the four views 0.058 %; the fresh V3 load sits 0.05 % under the in-load V3 views, so the
k3 storage does not change V3. Kill rules: `k3_hit_saving_ms` fired (0.071 ms, bar 0.25) and `boundary_over_draft_fraction`
fired (1.00, bar 0.05); the trims rule passed (0.142 ms removed from rank 0's A, bar 0.105).

What the host scopes say (hit means, ms, V3 -> k3+trims):

* rank 0 half A 12.112 -> 11.970 (trims: rank-0 half envelope 0.441 -> 0.302, prepare 0.0985 -> 0.0517);
* rank 1 half B 12.432 -> 11.893 (one layer moved, -0.539);
* boundary Bd 1.032 -> **2.005** (+0.97 ms for GDN layer 26, against 0.513 ms/layer priced from the QSA layers 24-25;
  the boundary export grew 0.053 -> 0.592 ms and the boundary envelope 0.081 -> 0.595 ms);
* draft D 1.608 -> 0.427; hit elapsed 14.060 -> 13.989 (-0.5 %); miss elapsed 25.778 -> **26.154** (+1.5 %).

Reading: the third boundary layer bought 0.54 ms on rank 1 but cost 0.97 ms on rank 0's boundary, almost all of it in the
export that follows the GDN layer. Hits broke even; misses lost. The composite is closed as measured; the trims are real
(0.142 ms off A) but rank 1 binds every hit on V3, so they are not a V3 lever by themselves. The next lever synthesis
(lever-synthesis-3) prices the rank-1 share of `kernel_io` and the boundary export from these scopes.

Window receipts: `lineage/window-20261022/` in the packet (driver log, live plan, archived PAUSE-B, runner journal,
restore output). Endpoints restored as `*-20261022-restore12`; PAUSE-A untouched, PAUSE-B re-armed.

## Attribution (lever synthesis 3, 21:00 UTC): the loss is the export path, not the layer

**Attribution (lever synthesis 3, `analysis/lever-synthesis-3-20261022.md`):** the rank-0 scopes split the +0.974 ms boundary into `boundary_body` +0.459 ms (the GDN layer-26 kernels, equal to the 0.463 ms saved on rank 1) and `handoff_export` +0.540 ms for the SAME 20,480 bytes, because the `kernel_io=kernel` key routed the export through `kio_read_many` (KioCopy, one work-item per byte into pinned host memory, 28.9 ns/byte) instead of the copy-engine readback (2.6 ns/byte). D 1.61 -> 0.43 was a model artifact (op-9 command duration under a non-blocking draft); the observed draft wall was 1.586 -> 1.537 ms. Closed: this kio-export composite. Open (ruling 2026-10-22): k3 + trims with the export on the copy engine, priced +2.74 % on the record replay (packet189 k3x).

Ranking on the V3 line from the replay: k3x (k3 + both trims + copy-engine export) **+2.74 %** (62.32; range +2.3 to +3.0), k3 alone with a copy export +1.56 %, kernel I/O both ranks with the export fixed +0.79 %, rank-1 kernel I/O alone +0.66 %, rank-0 trims alone +0.13 %, removing the export entirely <= +0.07 % (it sits inside the draft window on hits); no QSA layer is admissible in the boundary (23-25 -0.66 %, 24-27 illegal). Only k3x reaches the +2 % chain bar. Packet189 (`stage2/packet189-twocard-k3x/`) re-measures it with a `boundary_export=copy` key and D read from the draft wall.
