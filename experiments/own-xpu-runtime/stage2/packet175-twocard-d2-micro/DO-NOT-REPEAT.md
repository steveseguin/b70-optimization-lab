# Packet175 negative-result index (D2 dense-weight L2 warm-ahead)

No device result exists yet. This preparation closes nothing. The analyzer appends
a measured closure only after complete exact device coverage (240 interleaved
A/B pairs per layer, every timed arm byte-checked) and only if the weighted dense
GEMV time B/A, warm-ahead kernels included, is above 0.97 (coordinator review 44;
it superseded the original 4.8% rule before sealing). Synthetic adapter closures
live only under `evidence/private-report-cases/` and are not device conclusions.

Checked before work (see `evidence/do-not-repeat-search.txt`): packet119 warmed
selected DOWN bytes during bandwidth-bound gate/up (1.079x, closed); packet95/100
grid-word prefetch; packet125/138 route-predicted expert prefetch; packet142/145
order600 layout null; packet141 cold/warm ratios are streaming cost. D2 differs:
route-independent dense weights, warm issued before the GEMV. This micro tests
the separate-kernel form; its own time counts.

| Arm | Outcome | Evidence | Revisit condition |
| --- | --- | --- | --- |
