# Actual depth-two rolling inference: four-card correctness passed

The first actual rolling run used existing draft weights and native binary
`8e03d3cd67fc99c7db4408cb9c2e6abb158806f142df16292ece37083e706231`.
Plan `487f8d71c344e0053e602379fb9284006bd3c282c38de881a39519d19e58cdd6`
bound the source, model, draft, card layout and complete diagnostic policy.
The runtime received no expected-output or reference-token file.

All 32 output IDs, 2,065 target buffers and 73 canonical draft allocations
match accepted replay. All 117 canonical pairs and 32 actual recursive
predictions match retained evidence. The independent v6 audit checks raw wire
records, complete command histories, proposal provenance and sealed states.

| Owner | Tentative rows | Accepted | Discarded | Suffix aborts |
| --- | ---: | ---: | ---: | ---: |
| Stage 0 | 35 | 24 | 11 | 7 |
| Stage 1 | 32 | 24 | 8 | 7 |
| Stage 2 | 24 | 19 | 5 | 5 |
| Final stage | 0 | 0 | 0 | 0 |

Misses occurred at prediction depths one and two. Seven complete stage-zero
provider survival checks passed: five after canonical advancement and two
without advancement. Provider borrowing observed zero pending rows 94 times,
one pending row 23 times, and two pending rows zero times. The earlier forced
pending proof supplies separate two-row borrowing coverage; it is not attributed
to this actual run. Peak outstanding commands was three, which is a coordinator
observation rather than a GPU-utilization measurement.

All four workers exited zero. Across 75 passive samples, all 14 known fault
signatures stayed unchanged; minimum available host memory was 70,508,814,336
bytes. No power, memory, swap or cache setting changed. Diagnostic readbacks
were enabled throughout, so these timings are not a speed claim.

The full 181,102,788-byte archive is retained in tmpfs. The 2,948,137-byte compact
packet is saved and independently rehashed on USB. All 472,202,828 raw bytes
reuse exact raw/seal/index/state matches from the already durable portable-live
archive; all six restored sealed files pass the native reader. Originals remain.

[Proof](../experiments/own-xpu-runtime/research/continuation-2026-10-25/ring-rolling-depth2-proof/RESULT.md),
[independent receipt](../experiments/own-xpu-runtime/research/continuation-2026-10-25/rolling-provider-independent-review.json),
[durable archive](../experiments/own-xpu-runtime/research/continuation-2026-10-25/ring-rolling-depth2-durable-archive.json).

Next is persistent request reset, followed by an explicitly separate measured
policy that omits diagnostic readbacks while retaining arithmetic, checked
copies, rollback and error handling. Full state gates precede the cold suite.
Draft training remains prohibited.
