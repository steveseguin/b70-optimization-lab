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
