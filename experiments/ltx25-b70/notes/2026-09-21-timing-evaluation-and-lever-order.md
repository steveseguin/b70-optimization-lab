# Timing evaluation vs the 1.042 s/clip target, and the lever order (2026-09-21)

## Where the lane stands

| Quantity | Value | Source |
| --- | ---: | --- |
| Steady interval per clip (current best) | 1.63 s | f84/f86/f88 endure receipts |
| Effective fps | 15.3 | 25 / interval |
| Target interval for 24 fps | **1.042 s** | 25/24 |
| Gap to close | **0.59 s** | |
| Serial per-clip sampler time | ~1.98 s | three-stage-pipeline-01.md |
| Sampler pair stage (2 clips, pipelined) | 3.23 s | f87 receipt stage_seconds |
| Current pair overlap factor | 1.23x | 3.96 / 3.23 |
| Sampler weight-read floor | 0.74 s/clip | lossless-floor-and-audio-adaln.md |
| Block region per clip (serial) | 1.58 s | same |
| Non-GEMM work inside blocks | 0.84 s | same |

The sampler is the wall: 1.63 s/clip against a 0.74 s floor. The encoder
(sharded two-card) and decode are hidden under it.

## The lever order

1. **Packet 89: audio adaLN fusion** (built, gate-passing, awaiting a
   launchable boot). Proven bitwise-equal; ~0.05 s/clip. Ships with the
   120-prompt endure that also hunts the wrong clip.

2. **Pinned-host staging for the shard boundary (packet 90 candidate) —
   the big one.** The 2026-09-17 probes (`two-clip-sampler-design.md`)
   measured the exact variants on block-sized GEMM graphs:
   blocking device copies = **0.996x**; per-clip streams + events =
   0.996x; explicit device contexts + **activation staged
   device→pinned host→device = 1.68x**. The shipped shard still uses the
   losing variant: `ltx_layer_shard.py:42` does
   `value.to(device=device, non_blocking=False)` — a blocking peer copy on
   every cross-card boundary, inside every block replay, for every clip.
   The design doc's Route B already specifies the fix: stage the boundary
   activation through pinned host memory with events, issued under explicit
   per-device contexts. Probe-expected effect: the block region's two-clip
   cost drops from 3.16 s serial toward ~1.9 s; the pair stage from 3.23 s
   toward ~2.3-2.6 s; **interval toward 1.15-1.3 s/clip (~19-22 fps)**.
   Correctness: the staging changes *how bytes travel*, not arithmetic —
   oracle-gated end to end, and the existing receipts would catch any
   replay/transfer race.

3. **Then the floor fight (packets 91+):** with overlap at probe ceiling,
   the pair needs ≤ 2.08 s for 24 fps. What remains is the 0.84 s/clip of
   non-GEMM in-block work: more fusion in the audio path (attention on 26
   tokens is dominated by fixed kernel costs), norm-site consolidation on
   the video path, and the glue capture items from the heartbeat list. Each
   is small; they are the last 0.1-0.2 s.

## What does NOT move the number

- The transformer split point: packet 84's 23/25 rebalance measured 1.63-1.65
  vs the 1.62 control — noise. Closed.
- More clips in flight beyond two: the sampler cards are the serialized
  resource; depth hides other stages, not the wall itself.
- Anything touching the 0.74 s weight-read floor: unreachable losslessly.

## Verification plan for lever 2

Packet 90: `_move` replacement behind the same CACHE_KEY discipline,
per-device contexts already present in `_BlockRoute`. Warm exactness gate +
30-prompt tsh + 120-endure. Success = all_exact and steady_mean ≤ ~1.3 s.
The probe data says the risk is the driver's peer path, which the staging
bypasses entirely (D2H pinned, H2D pinned — both ordinary copy-engine ops).
