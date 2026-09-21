# Timing evaluation vs the 1.042 s/clip target, and the lever order (2026-09-21, corrected)

## Where the lane stands

| Quantity | Value | Source |
| --- | ---: | --- |
| Steady interval per clip (current best) | 1.63 s | f84/f86/f88 endure receipts |
| Effective fps | 15.3 | 25 / interval |
| Target interval (24 fps) | **1.042 s** | 25 / 24 |
| **Gap** | **0.59 s per clip** | |
| Sampler stage per pair | 3.23-3.26 s | two-clip note, probe-5 receipts |
| Serial sampler per clip (single clip) | ~1.98 s | three-stage note |
| …of it transformer blocks | 1.58 s | block table |
| …of it non-GEMM (norms, small kernels) | 0.84 s | block table |
| Read-only floor (weights, both cards) | 0.74 s/clip | scale model |
| Decode wall per clip | 0.71 s | f84 receipt (fully hidden by pipelining) |

## Corrections to an earlier draft of this note (kept honest)

- **Pinned staging is already shipped.** `staged_move` (ltx_graph_capture.py:546,
  probe-5's exact 1.68x recipe: D2H into pinned host on the source thread
  stream, event, host wait, H2D on the destination thread stream) is wired at
  every graph-route boundary (lines 789-801) and in `_staged_cached` for
  per-forward args. The blocking peer copy survives only in the *eager* shard
  path (`ltx_layer_shard._move`) and in `_staged_cached`'s non-tensor fallback.
- **Phase timing is already persisted.** The sampler receipt
  (`pipeline-sampler-<run_name>.json`, line 315) embeds `emitted_phases` - the
  per-clip GPU-event deltas for every emitted clip. No new measurement code is
  needed; the next endure campaign produces the profile.

So realized overlap today: serial pair ~3.96 s vs stage wall 3.23 s = **1.23x**,
against probe 5's synthetic 1.68x. The missing 0.45x is the whole game, and it
is *not* the transfer path.

## Where the gap can live (hypotheses, ranked by prior)

1. **Serial chain length inside each clip.** A clip's own chain is
   stage_a → upsample → stage_b → audio; only the *other* clip can fill a
   card while this one waits. Two clips × two cards leaves the cards idle
   whenever both clips are simultaneously in a non-sampler stage (encode,
   VAE, upsampler on the wrong card) or in the same-card phase. Probe 5 had
   no upsampler and no third stage; 1.68x is its ceiling, not ours.
2. **Host-side boundary waits.** `staged_move` blocks the *host thread* on
   `event.synchronize()` at every boundary; that thread then cannot issue the
   next segment's work while it waits, even when the destination card is
   idle. A `stream.wait_event` variant keeps the host issuing.
3. **Non-GEMM time not overlapping.** 0.84 s of per-clip block time is norms
   and small kernels; if both clips hit their small-kernel regions in phase,
   neither hides the other.

## Lever order

1. **Packet 89 (built, gated, ready):** adaLN fusion, bitwise-proven, ~0.05
   s/clip. Its 120-prompt endure arm doubles as the wrong-clip hunt and as
   the profile source: every sampler receipt carries `emitted_phases`.
2. **Packet 90 - read, then fix:** aggregate `emitted_phases` across 89's
   endure receipts (stage_a/mid_wait/stage_b/audio/refill ms per clip) plus
   `stage_seconds`, and compute per-card occupancy. Decide by evidence:
   - GPU-ms per pair ≈ wall per pair → cards are the wall: attack kernel
     time (more fusion, attention backend, adaLN count), not transport.
   - GPU-ms ≪ wall → host serialization: `stream.wait_event` variant of
     `staged_move`, then re-measure with the probe harness first.
   - Cards idle in matching windows → pipeline depth (a third clip in
     flight) is the only remaining structural lever; needs xpu:1/xpu:3
     headroom review (xpu:3 carries the encoder shard).
3. **Then the floor:** 0.74 s/clip weight reads. The unrealized-overlap fix
   plus fusion realistically lands 1.1-1.3 s/clip; closing the rest is
   kernel-count work, itemized from the block table's non-GEMM 0.84 s.

## Sanity math for 24 fps

1.042 s/clip with the pair stage ≤ 2.08 s. Probe-5 scaling on blocks alone
gives ~1.9 s of block GPU time per pair at 1.68x; adding ~0.4-0.8 s of
non-overlapped per-clip work says 24 fps needs *both* the overlap fix *and*
a cut in per-clip GPU time. That is the honest statement: 24 fps is not one
lever away, it is two or three.
