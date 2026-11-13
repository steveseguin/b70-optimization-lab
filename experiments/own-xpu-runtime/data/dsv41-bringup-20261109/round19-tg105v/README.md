# Round 19, gate tg105v (tp104, 2026-11-12 19:00-19:20): the draft's candidate vocabulary on all five prompts

`OWN_DR_VOCAB=dsv41-work/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000` (draft-only: the draft picks guesses
from a candidate list; the checked answers cannot change). BEST = blocks of 64 + DSpark guessing depth 5, TAU 0.5.
Alternated A / B, B / A over two rounds; vocabulary + TAU 0.40 once. All 25 runs SAME AS the plain run.

| prompt | BEST | + vocabulary | change | + vocabulary + TAU 0.40 |
|---|---|---|---|---|
| code | 144.31 / 143.51 | 145.49 / 144.86 | +0.9 % | 150.33 (+3.6 %) |
| analysis | 159.34 / 159.77 | 162.55 / 161.17 | +1.4 % | 159.42 (-1.5 %) |
| prose | 120.63 / 119.35 | 121.34 / 121.95 | +1.4 % | 120.83 (-0.7 %) |
| docs | 149.39 / 145.91 | 150.40 / 150.74 | +2.0 % | 148.73 (-1.2 %) |
| ops | 141.74 / 141.41 | 139.36 / 142.85 | -0.3 % | 142.95 (+1.3 %) |

**Decision:** the vocabulary joins BEST from the next gates (about +1 %, never worse beyond noise). TAU stays 0.5
(0.40 mixed for the third time: helps code only).
