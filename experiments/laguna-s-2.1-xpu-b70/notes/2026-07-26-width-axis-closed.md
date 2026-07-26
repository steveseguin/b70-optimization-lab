# Laguna — the width axis is closed; width 12 is the optimum

Date: 2026-07-26 America/Toronto

## Four measured widths, same session, same suite

| width | depth | emitted/cycle | derived cycle | scored tok/s | exact |
| ---: | ---: | ---: | ---: | ---: | --- |
| 8 | 7 | 3.7010 | 39.03 ms | 94.822732 | 13/13 |
| **12** | 11 | 3.9552 | **39.35 ms** | **100.524890** | **13/13** |
| 14 | 13 | 3.9911 | 41.05 ms | 97.225922 | 12/13 |
| 16 | 15 | 3.9637 | 45.09 ms | 87.899434 | 0/13 |

## Cycle growth accelerates, and it beats the acceptance gain

| step | ms per width |
| --- | ---: |
| 8 → 12 | 0.08 |
| 12 → 14 | 0.85 |
| 14 → 16 | 2.02 |

Width 14 buys **+0.91%** emitted per cycle for **+4.32%** cycle time: a net loss
of 3.3%. The geometric acceptance tail is nearly flat past depth 11 while the
wider verifier gets steadily more expensive, so the product peaks at width 12.

This also retires a doubt about the width-16 timing. That run failed exactness,
so its 45.09 ms was suspect as a slope source. Width 14 is measured
independently and sits on the same accelerating curve, so the shape is real.

## Exactness degrades with width, it does not fail abruptly

Width 14 is **12/13** — a single prompt diverges. Width 16 is 0/13. So the
defect is not width-16-specific: it appears at 14 and is total by 16. Width 12
is clean at 13/13 across three separate runs today.

Worth noting for anyone tempted by the wider widths later: whatever the defect
is, it is subtle at 14 and would be easy to miss without a bitwise gate. A
throughput-only comparison would have called width 14 a modest regression and
moved on, never learning that one of its thirteen answers was wrong.

## Consequence

Depth is exhausted as a lever. Every remaining approach to 102 has to raise
**acceptance at width 12**, not widen the verifier. That leaves the tree.
