# 2026-10-22 — packet191: per-class kernel cost on both ranks of the k3x record line (CPU-prepared, device pending)

**Packet:** `experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/`. **Parent:** packet189 (k3x screen; the
packet190 record 62.345282 tok/s uses its selection `c5443bbf…` and engine `87eec645…`). **Kind:** a MEASUREMENT (priced gain
0 tok/s), on the coordinator's ruling from lever synthesis 4 (quoted in the README): both ranks are 99.3 % busy per hit, every
class sits at its ledger floor, and only a both-ranks per-GDN-layer kernel saving of ≥ 15.1 µs can still reach +2 % (3.8 µs
for +0.5 %). The line has no in-engine per-class table under its current selection (packet77 is bundle-6-era, packet110 is a
synthetic layer, packet128b's all-events attribution was withheld at 0.728 overhead).

## What was built

* **An in-load view key `sites=off|on`** on the k3x selection, both ranks (`v5/sites-native.patch`, +69 / −17 lines in 8
  files; new header `v5/native/p191_sites.hpp`). `on` records, inside the sampled halves (fixtures 9-16, 57-64, 105-112 of
  each request), the site label of every issued kernel event and, at the half's own final drain, reads the event's device
  start/end timestamps from the profiling queue the rank already runs and writes one `packet191.site.v1` row per event
  (rank, half, phase `half|boundary|draft`, fixture, position, speculative, corrected, label, start_ns, end_ns). No kernel,
  no barrier, no device readback. `off` (and the 19-key record selection) is the record path plus one bool test.
* **Lineages** `k3x-off` (`eaba9647…`, the k3x choices + `sites off`, 20 keys) and `k3x-on` (`3fee7f49…`); `k3x` unchanged.
* **Rows (lane B, proposal only, never queued):** row 0 k3x-on smoke 12 × 64 + incident64 (~313 s); row 1 ONE load of
  k3x-off, views off/on/off/on/off, 12 × 128 each (~480 s). Watchdog 3600 s each; ≈ 854 s total.
* **Report `s191_report`** (not a win/loss screen): per rank, per phase, per class: ms per half, µs per GDN and QSA layer,
  excess over the 537 GB/s copy floor (packet72/77 byte formulas on the pinned header census) and over packet110
  (`roofline.json` @128), per-site rows; a class is lever-eligible by excess only at ≥ 15.1 µs per GDN layer on BOTH ranks
  (3.8 µs screen), listed with the DO-NOT-REPEAT closures of its mechanism families and the open mechanisms (none registered
  for any class), so the outcome says explicitly whether a +2 % kernel brief can be priced. Kill rules: exactness/proposals;
  off drift > 0.5 %; on/off < 0.93 withholds the table (packet128: never ratio-corrected); class sums vs `layer_body` /
  `half_completion` > 10 %; leaked rows in an off view; a request without rows on either rank; an unclassified label.

## CPU evidence (all gates PASS; nothing queued, launched or committed)

* Build: device engine `cd199292efe810b8ad0d767193f5788605ef3b93a06925e9061819f66c6ddea9` (gnu-host twin `8c552f31…`), 8
  compiler runs, 0 warnings, 78 parent objects pinned.
* Production-shape startup: 12 loads × 2 ranks incl. the two sites loads in both start orders; captures and census identical to
  packet188/189; `sites=on` device delta 0 B per rank; 23 native refusals per run (`sites: unknown` added); the engine's own
  row-format proof on the real plan (rank 0: 20 GDN sites + PLE on layer 1, boundary layers 24-26; rank 1: 20 sites, head,
  draft) — every label classifies.
* Byte identity: canonical transcripts (every rank-0 allocation and the exported slot after every step) identical for the
  19-key k3x, k3x-off and k3x-on (GNU) and k3x-on (Intel): `d451302d…`, = packet188/189's; 44 two-rank miniature requests in
  both start orders equal the reference.
* Analysis on REAL data: packet189 row 1's two k3x views as off views (1,188 intervals each; no site rows), packet190's record
  chain WS128 (932 hits / 256 misses), and synthetic instrumented views on packet189's real streams with packet110's call
  times through the real report path: packet110 reproduced (experts ≈ 111 µs, dense ≈ 155 µs per GDN layer; experts 74 µs
  over the floor), completeness 4-5 % against the real bodies, six classes flagged by packet110's own excess with their
  closures and no open mechanism; 0.92 overhead withholds the table.
* Memory: rank 0 31,374,119,922 B (headroom 838,134,798 B), rank 1 31,581,735,626 B (630,519,094 B); host admission
  108,797,048,558 B + 1 GiB.
* Disk: root stayed above the 27 GB floor throughout (≈ 29.9 GB free at the end); the packet is 160 MB apparent, mostly
  hard links of packet189's history; packet189's 440 MB device rows are read in place and pinned by sha256.

## Rows checked (DO-NOT-REPEAT)

All 223 DO-NOT-REPEAT.md files under stage2 grepped for the class families and for "attribution" (`analysis/dnr-class-grep.txt`).
No row closes an in-engine per-class view on the k3x line. The rows that bind the analyzer: packet128 ("A failed overhead gate
withholds rankings. Do not correct event times by a throughput ratio."), packet140 row 4 (packet128b withheld at 0.728),
packet77 (sum stages per call, refuse zero-duration events), packet140 row 3 (packet110 is not an attainable floor), packet157
(an absent stream is never a zero). packet142 closes the one item lever synthesis 4 left "open on paper" (packet104b).

## Next

The device window (lane B, both rows, < 15 min). If the overhead gate fails, record fewer fixtures (one window) — never scale.
If a class is lever-eligible by excess with a mechanism no row closes, that mechanism gets the next brief; otherwise the
two-card kernel lane is closed at 62.35 until a new mechanism exists (lever synthesis 4 §5).

## Device result (2026-10-23, lane B window 00:32-00:47 UTC, unit lanequeue-B37): exact; class table withheld

Measured 2026-10-23 (lane B, lanequeue-B37, 00:32-00:47 UTC): every view 13/13 exact, proposals and acceptance identical; sites-off 62.198/62.166/62.184 (−0.08 % vs packet189 k3x, −0.26 % vs the record chain; drift 0.05 %); sites-on 58.266/58.238 (instrumented/control 0.937, just above the 0.93 bar; +0.78 ms per rank-0 half, +0.71 ms per rank-1 half = ~32 µs per layer of recording cost). **Class table withheld: the `class_sum_vs_body_pct` kill rule fired (device kernel sums 11.44 ms per half vs the host `layer_body` scope sum 16.40 ms, −30 %)**; the reference quantity is host-side layer scopes that overlap each other while the host runs ahead of the device, so it is not comparable to device kernel sums (the analyzer's completeness rule, not the device). Raw sampled windows retained in `s191_report.attribution`: per layer (rank 0 / rank 1, µs): dense 154/154, experts 105/105, route+small 76/76, HC 68/68, recurrence 30/27 (per layer, ~40 per GDN layer), QSA attention 17/20, norms 16/16; sum 11.36 ms (rank 0) / 9.77 ms (rank 1) per half. Against packet110 (experts 111, dense 155, HC 84, route+small 54, recurrence 38): only route+small reads higher (+22 µs/layer on both ranks), but that class is many tiny kernels and absorbs the ~32 µs/layer recording cost, so it is not a measured excess. `eligibility` and `open_mechanisms_remaining` are empty.

What the measurement did establish: (1) the record line reproduces in a one-load bracket after the chain (62.17-62.20 vs 62.35 chain, 62.24/62.23 packet189); (2) the sampled recorder costs ~32 µs per layer per half and lands the instrumented/control ratio at 0.937, at the packet128b-style overhead edge; (3) per-rank class sums are 95 % (rank 0) and 82 % (rank 1, whose half also holds the head and the draft) of the off-view halves, consistent with the kernel-floor picture of lever synthesis 4; no class shows a measured excess over packet110 once the recording cost is allowed for. Next step if the class family is pursued: a kernel-count/batched-event recorder with ≤ 5 µs per layer cost and a device-side completeness reference (sum of per-layer first-to-last kernel spans), run as a new packet; nothing in this packet is reusable as a lever.

Window receipts: `lineage/window-20261023/`; endpoints restored as `*-20261022-restore15`; PAUSE-A untouched, PAUSE-B re-armed.
