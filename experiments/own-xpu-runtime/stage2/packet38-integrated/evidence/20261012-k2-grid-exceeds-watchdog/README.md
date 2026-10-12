# K2 stopped by the coordinator: its QSA grid would have run past the window's own watchdog (2026-10-12 14:34–15:18 UTC)

K0, K1a and K1b had passed. K2 times QSA attention at every context length from 88 to
152 plus 256 (66 shapes), five implementations each, 200 repetitions; one shape takes
about 3.6 minutes on the card, so the grid needs about four hours, more than the
window's 10,800-second watchdog, before the GEMV classes even start. After 44 minutes
and 12 shapes the coordinator sent one interrupt to the wrapper process (not to the GPU
process); the wrapper wrote its cooperative stop request, the native program finished
its current repetition and exited cleanly within a second; no kernel fault line. The
wrapper recorded "coordinator stop requested" and wrote no fault latch.

The partial timing is kept ([events](k2-partial-events.jsonl.gz)) and already answers
the question the grid was for. QSA attention at capacity 256, µs per group, medians of
200:

| Context length | round 2 | `p33.qsa.shape` | `p30.attention.score_softmax` | `p30.attention.sg32` |
| ---: | ---: | ---: | ---: | ---: |
| 88 | 245.8 | 204.1 | 120.1 | **100.6** |
| 113 | 294.6 | 241.5 | 152.4 | **125.1** |
| 128 | 320.7 | 260.6 | 162.0 | **135.5** |
| 136 | 347.4 | 283.8 | 182.6 | **148.6** |

(The harness's packet 18 row measures about 1 ms and is not the in-model path, which
takes 265 µs per QSA layer at these lengths.) `p30.attention.sg32` is the fastest at
every length measured and grows by about 1 µs per context position.

Fix: reduce the grid to a handful of lengths and rerun (packet 38's follow-up seal).
