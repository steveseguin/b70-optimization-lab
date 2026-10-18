# Packet144 miss-path study — closeout

<!-- campaign-closeout -->

## Question and identity

On October 18, could a new exact miss-path mechanism plausibly improve the
two-card bundle8 record by at least 3%, with supported transfer? Unchanged
quantized compressed Unsloth UD-IQ3_XXS target, `iq3-p49-split32-v1`, BF16 KV,
24/24 layers and rank1 MTP. CPU study on steve-b70s; no device experiment.
The complete identity and ranked table are in [ANALYSIS.md](ANALYSIS.md).

## Outcome

**Closed at the ranking gate; no mechanism qualifies.** The calculator
reproduces bundle8's 58.798108759182306 tok/s and bundle7's 58.2238342935355
from their original saved receipts. Bundle8 requires 2.337708 ms net saving
on each miss for +3%. Hiding all restore gives +0.691%; B-only removal on
misses gives +0.916%. Completing omitted draft-head rows has a +1.233%
retrospective ideal sensitivity, even granting all 20 eligible misses a free
rescue. None is a measured candidate gain.

Correction-only cooperative execution has a larger work budget, but no
supported net transfer or admitted memory plan. A favorable assumed number
cannot pass the gate. No implementation, vendor copy, lane-B smoke/v5 proposal,
entry rehearsal or READY-FOR-DEVICE marker was created. Packet132 remains
closed at its original +3% gate.

## What worked

The study uses bundle8's own 1,188 intervals instead of transferring old
record timings. It preserves the exact class aggregation and separates
per-miss savings from work already overlapped. The full 176-file negative
index scan and frozen source proof prevent reopening old draft, restore,
placement and wrong-token reuse claims under new names. Independent read-only
review confirmed the dependencies and numerical reconstruction; its wording
refinement made all component-only bounds explicitly conditional.
The final calculator used 166,736 KiB peak RSS (about 163 MiB), below 4 GiB.
The document check resolves 26 local links and confirms all seven captured
packet136 source/selection/index files still match their saved hashes.

## What failed or remains uncertain

No candidate was built or timed; no new device correctness pass exists.
Cooperative rows need communication/memory/ownership evidence. Cache warming
needs measured residency and effects beyond a B-only change to be interesting.
Early loss detection cannot identify the corrected global winner. Whole-layer
handoff and further exact drafting lack inputs. Existing profiling overhead
prevents interpreting the larger gaps as normal record headroom.

The calculator's first local run rejected an inappropriate 0–11 upper search
range for a fractional rescue parameter; the fraction search is now bounded
to 0–1, separately from the millisecond search. Final reconstruction/checks
pass. This was an analysis-only error, not runtime or GPU work.

## Evidence and patches

- [Ranked analysis](ANALYSIS.md), [calculator](analyze.py),
  [computed model and audit matches](model.json),
  [frozen source/audit inputs](inputs.json.gz).
- [Analysis validation](evidence/analysis-check.json) and
  [resource receipt](evidence/analysis-resources.txt),
  [document/source check](evidence/document-check.json).
- [Negative decision index](DO-NOT-REPEAT.md) and
  [work note](../../../../notes/2026-10-18-own-runtime-packet144.md).

The 263,791-byte gzip retains exact source and all negative indexes, including
the pre-existing dirty packet128b budget's observed text. Decode with standard
gzip/JSON and verify each UTF-8 text's SHA256. Original record archives remain
at their tracked paths and are hash-bound, not duplicated. No artifact was
deleted. Total packet retention is below 1 MiB; no model data is retained.

## When to revisit

A new exact mechanism must support at least 2.338 ms net per miss, or an
independently demonstrated miss-rate improvement with its complete cost.
Changes affecting multiple critical components need their own dependency
model and transfer evidence. If that gate passes, use a separate packet136
copy, prove runtime switching, rehearse its real entry, propose smoke before
one-load v5 and write READY-FOR-DEVICE last. This bounded study is closed;
the model lane and separately owned experiments continue.
