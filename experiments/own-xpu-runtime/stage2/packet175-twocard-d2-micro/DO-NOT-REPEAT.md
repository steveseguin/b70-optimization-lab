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
| D2 dense-weight L2 warm-ahead (separate warm kernel before every dense GEMV, real packet166 M1 launch order + 256 MiB interposer) | packet175 device micro: weighted reduction -43.86% including warm time, B/A 1.4386 > 0.97; GEMV-only median per layer L0 14.97%, L3 5.55%; warm alone L0 0.198 ms/row, L3 0.210 ms/row. Evidence /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet175-twocard-d2-micro/evidence/d2-micro-B1. | A warm-ahead that costs no serial device time (folded into a latency-bound predecessor) AND a measured GEMV-only reduction of at least 3% on its own. |
