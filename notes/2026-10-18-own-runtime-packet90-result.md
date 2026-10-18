# Packet 90 result: lane-B grid (2026-10-18 02:23 UTC)

Lane B (cards 2+3), shared pinned v4, `--direction B-grid`. All four screens passed. The control is packet 84's selection (hc-wide, wide64, ordered, rec-parallel).

| # | View | tok/s (class-balanced median) | vs control mean (55.503) |
|---|---|---|---|
| 0 | production | 55.517 | — |
| 1 | E1 `exp-halfcache` (exact FP32 half-scale cache in the IQ2 gate/up repack) | 55.657 | **+0.28%** (beats both controls) |
| 2 | H1 `hc-weightcache` (FP32 `scale*float(code)` HC up/gate weights) | 53.701 | **−3.25%** |
| 3 | production | 55.489 | — |

## Decisions (coordinator, review 13 rule)
- **E1 is closed as a standalone lever:** under +0.5%, so no lane-A confirmation of its own. It stays available as an exact composition option if a later bundle confirms it there. Packet 86 `exp-nodeq` bounds expert dequantization at about 1.14 ms per half; E1 captured under 10% of it. Next expert designs: packet 95 (E3 grid-prefetch, E2 scale-cache) per packet 90's preregistration and the remaining packet 86 views.
- **H1 is closed (DO-NOT-REPEAT):** FP32 HC weights quadruple the gate bytes, and the bandwidth cost far exceeds the conversion saving (`hc-nodeq` bounds conversion at about 0.36 ms per half). Further HC work should cut conversion without growing bytes (H2 scale broadcast, or packet 94's norm fusion for the launch-bound norms).
- After the post-submission fix to packet 84's `packet56_submission.py`, the comparison helper refused with "sealed file changed". The file was restored (`6470679d0`).
