# Packet191 negative-result index (k3x class attribution: per-class site instrumentation on both ranks, in-load view key)

No device result exists yet. After the window, append the row from row 1's `bracket-summary.json` → `s191_report` (or
`python3 -B v5/s191_report.py <rows 0..1>`). This packet is a MEASUREMENT: no row of it is a speed result or a record row.

## Ruling (coordinator, lever synthesis 4, 2026-10-22, quoted)

> "Lever synthesis 4: on the k3x record line both ranks are 99.3% busy per hit and every kernel class sits at its ledger
> floor; the only family that can still reach +2% is per-layer kernel cost on both ranks (+1.32% per 0.01 ms per GDN
> layer; +2% needs 15.1 µs per GDN layer, +0.5% needs 3.8 µs). Build packet191 as a measurement: the record k3x selection
> unchanged plus packet77-style per-class site instrumentation on both ranks as an in-load view key, so each class's
> per-rank cost and its excess over the copy floor and over packet110 are measured on the line that holds the record."

## Rows checked before work (quoted; packet189's rows carried, plus the attribution search)

* **All 223 DO-NOT-REPEAT.md files under stage2** (`analysis/dnr-list.txt`, `analysis/dnr-class-grep.txt`) were grepped
  for every class family the report can flag (experts gate/up/down, tile16/half-cache, down-warm, IQ2 lookup; dense packed
  reads, S1/D1/D2; QSA attention/local sharing; recurrence rec-head/rows4; HC gates/norms/low, norm-consumer fusion, HC
  remap; route/router/top10/route fusion; head transpose/argmax; class and kernel-order layouts) and for "attribution",
  "sites.jsonl", "per-class", "instrumented". No row closes an in-engine per-class attribution view on the k3x line;
  packet77 is its precedent. The rows that bind this packet's analyzer:
  * **packet128 (2026-10-18):** "A failed overhead gate withholds rankings. Do not correct event times by a throughput
    ratio." and **packet140 row 4:** "Treat packet128b's instrumented class times as a bundle8 speed result | Invalid:
    overhead gate failed [0.728]; ... Revisit: Passing low-overhead matched attribution, preserving the old diagnostic
    receipts." → `s191_report` withholds the whole class table when instrumented/control < 0.93 and never scales an event
    time by the ratio; the instrumentation samples 24 of 127 fixtures to stay low-overhead (packet128b recorded everything).
  * **packet77 (2026-10-17):** "Event median as multi-stage call cost | Invalid. Sum stages within each call, then take call
    median." and "Zero-duration compute event | Refused." → every site's events are summed per call before any median; a
    zero/negative compute event refuses the view.
  * **packet157 / packet189:** an absent stream is never a zero → the per-half class sums must match the half body within
    10 % (kill rule 4) and an `off` view that writes site rows, or an `on` view with a request without rows on either rank,
    stops the report.
  * **packet140 row 3:** "Use packet110's 5.41 ms reference as an attainable bundle8 floor | Invalid: representative
    pre-down-tile16/pre-fusion useful-byte model, not an ordinary current half measurement." → packet110's numbers are a
    comparison column (excess over packet110), never a floor; the floor column is the 537 GB/s copy reference on the
    packet72/77 byte formulas, reported as a reference gap, not a realizable saving.
* **packet189 boundaries** (all respected): layer 26 (24-25) runs only inside the boundary command after the accept; no QSA
  layer in the boundary; the export stays on the copy engine (`boundary_export copy`); D is the draft wall; no record chain
  below the chain rule, no screen submitted. The k3x execution keys are the record values in every packet191 view.
* **packet188 / 186 / 187 / 185 boundaries**: as carried by packet189 (no speculative moved layers, no slim layout, no
  in-load head switch, prepared inputs admitted by the measured gains). The only key that switches in-load here is `sites`.
* **Class closures named by the report** (`s191_report.CLOSURES`, from the corpus grep): experts (packet65 in production;
  73, 81, 95, 104/104b "do not rerun that arm" (packet142), 119, 162, 173, 102/115, 142/145), dense (74 "no repeat without
  a new unpack mechanism", 93/93x, 183 S1 −6.2 %, 175 D2, 175b D1, 113), QSA attention (107, 116), recurrence (82/82b in
  production, 67 rec-head, 49d), HC (60 "do not reopen", 73, 94, 117, 122, 140, 67 "do not repeat without measured in-engine
  GB/s per site"), norms (78, 94), route/small (78, 109 in production; 112 "Forbidden", 164 "Not identifiable"), head (93,
  161), draft (158 lane closure). **No open mechanism is registered for any class** (lever synthesis 4 §2.2; packet142
  closes the one "open on paper" item, packet104b).

## Measured (pending)

| Date | Arm | Outcome | Revisit only when |
| --- | --- | --- | --- |
| pending | **k3x class attribution on the record line:** the record k3x selection + `sites=on` (both ranks, sampled fixtures 9-16 / 57-64 / 105-112, every site of every layer, the boundary and the draft; device timestamps read at the half drain). Rows: k3x-on smoke, one-load off/on/off/on/off (lane B); report `s191_report` (per rank / phase / class: ms/half, µs per GDN and QSA layer, excess over the 537 GB/s copy floor and over packet110; lever-eligible by excess ≥ 15.1 µs per GDN layer on BOTH ranks, 3.8 µs screen; closures named; kill rules exact / off drift > 0.5 % / on-off < 0.93 withholds the table / class sums vs body > 10 %) | pending device window | — |

## Boundaries (do not)

* **Do not read an instrumented view's rate as a speed result**, and do not compare `on` views with the record. The `on`
  rate is only the overhead gate's numerator; the `off` views are the record path and are compared with packet189's k3x
  views (62.242 / 62.225) and the packet190 record (62.345282) for timing equivalence only.
* **Do not correct event times by the instrumented/control ratio** (packet128). A ratio below 0.93 withholds the table;
  the fix is less recording (fewer sampled fixtures), never a scaled table.
* **Do not treat the "excess over the copy floor" as a realizable saving.** It is a reference gap on useful bytes (packet110's
  convention: cached duplicate loads, lookup tables, overfetch and transactions are not counted). A class is "lever-eligible
  by excess" only on the arithmetic of the ruling; whether a mechanism exists is the DO-NOT-REPEAT question, answered per
  class in the report.
* **Do not record every fixture.** packet128b (all events) measured 0.728 and withheld; the three eight-token windows are
  the design. Do not read host memory, add a kernel or a device readback for the attribution: the recorder is a host map of
  event ids and the timestamps are read after the half's own final drain, on the profiling queue both ranks already run.
* **Do not load the 20-key `k3x-off` selection as a record selection.** The record selection is the 19-key `k3x`
  (`c5443bbf…`); `k3x-off` (`eaba9647…`) exists so the in-load switch has a key to switch; the engine proves they are the same
  path (canonical transcripts identical), and a record chain keeps using `k3x`.
