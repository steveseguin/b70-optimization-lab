# K2 port and selection review

CPU-only implementation review; this report is not an independent review of
its author's own changes. The independent dense agent reviews this code.

Packet35's measured fusion-vs-selected-member rule is retained and corrected
in two respects. Every small fusion is evaluated, including one whose initial
comparison against its R5 control did not pass the individual 10% threshold,
and one with no dispatch conflict. HC attention and FFN sites are compared
separately because their low/inject kernels are independently selected. A
single enabled fusion must beat both sums; aliases are not extra operations.
This second correction came from the independent dense agent's review.
Ties choose members. Missing or nonfinite costs fail closed. A byte-failed
fusion cannot be selected. Every required Q6/Q8 workload must win.

The K2 control is the recorded packet29 selection, copied as
`dispatch-incumbent.json` and represented by `k2_incumbents.hpp`. Each comparison
retimes that incumbent; no historical duration is reused. R5 remains a measured
candidate wherever the incumbent changed. Packet25/27/28/29 alternatives are
retained and the five admitted packet33 names are added. Routed rank4 is not
registered. The 34 actual runtime shape/format workloads remain full size;
payloads above 8,000,000 bytes use eight rotated copies plus reread diagnostics.
Two hundred repetitions and pre/post byte equality are unchanged.

Both K1 and K2 use the common fixture driver, so all linked GEMV alternatives
and packet33 QSA are checked by each fresh K1 owner. K2 emits the measured map
and identical rank0/rank1 maps: this is a common dispatch policy measured on
one card, not independent measurements of two cards.

`test_k2_selection.py` records synthetic regression tests for cheaper fusion,
cheaper members, ties, both HC sites, disabled/no-conflict fusions, aliases,
failed bytes, missing timings, nonfinite timings, format regressions, the
closed vocabulary, and packet29 incumbent identity. Actual device timing and
byte-equality admission remain pending K0/K1/K2 windows.
