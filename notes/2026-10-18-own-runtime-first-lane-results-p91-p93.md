# First-lane results: packets 91 and 93 (2026-10-18 03:15 UTC)

All screens use the shared pinned v4 wrapper, 128 tokens, 13/13 exact gate, and class-balanced tok/s (median of six prompt-class medians, intervals 1–100). The control is packet 84's selection (the record line).

## Packet 91, lane A grid (cards 0+1)
| View | tok/s | vs control mean (55.388) |
|---|---|---|
| control | 55.386 | — |
| route-fast | 55.501 | +0.20% |
| rec-both-plus | 55.411 | +0.04% |
| **route-fast + rec-both-plus** | **55.744** | **+0.64%** (beats both controls) |
| control | 55.390 | — |

The combination is larger than the sum of its parts (+0.24%). Lane-B 3-view confirmation (`packet91-B-confirm-0..2`) is queued after the packet 86 diagnostics.

## Packet 93, lane B grid (cards 2+3), micro-B2 qualified
| View | tok/s | vs control mean (55.453) |
|---|---|---|
| production | 55.396 | — |
| **head-transpose** (block-transposed packed Q6_K target head) | **55.928** | **+0.86%** (beats both controls; acceptance 0.787 unchanged) |
| production | 55.510 | — |

The microbenchmark saved 0.384 ms per head (1.417 → 1.033 ms). In the engine, rank 1's step dropped 0.177 ms (about 47% transfer). Lane-A confirmation (`packet93-A-confirm-B2`) is queued next on lane A.

## Composite (packet 97, review 14 rule)
Both packets now have one exact first-lane win against both controls, so they qualify for the packet 97 composite screen on both lanes.
