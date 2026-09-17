# Packet 65: fast path + save-behind, 2.029 s per distinct clip, exact; the block region is now the wall

*2026-09-17 04:47–04:54 UTC, server PID 22356, boot `09862e00…`. Evidence:
[`data/graph-capture-65/`](../data/graph-capture-65/), committed after every
arm. Ten distinct prompt/seed fixtures, every emitted clip compared with its
own reference.*

| Arm | Prompts | Distinct | Exact | Steady interval | p95 | min–max | fps equiv |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| warm clip (`pipe`, boat) | 1 | 1 | yes | — | | | |
| **`pipe-fast-save`** (resident fast path + MP4 written on the decode worker) | 20 | 19 | **19/19** | **2.029 s** | 2.34 s | 1.95–2.41 | **12.3** |
| `pipe-fast` (repeat of packet 64) | 20 | 19 | 19/19 | 2.140 s | 2.42 s | 2.05–2.43 | 11.7 |
| `pipe` (control, after the candidates) | 12 | 11 | 11/11 | 2.499 s | 2.76 s | 2.17–2.76 | 10.0 |
| `pipe-fwdtimed` (diagnostic, device syncs around every forward) | 12 | 11 | 11/11 | 3.516 s | | | not a speed result |

The control reproduces packet 58 (2.519 s), the fast-path repeat reproduces
packet 64 (2.135 s), and save-behind adds a real 0.11 s on top. Nothing is
cached, reused, approximated or reordered; the MP4 preview is the same
container, codec, fps and colour space, written from the same decoded frames
one thread over.

## Where the 2.03 s now goes

Per-forward wall with the cards synchronised before and after (11 clips):

| | per forward | per clip |
| --- | ---: | ---: |
| stage A (64 video tokens), 8 forwards | 0.139 s | 1.11 s |
| stage B (256 video tokens), 3 forwards | 0.181 s | 0.54 s |
| **all forwards** | | **1.67 s** |
| captured block region (packet 29 real-block timing) | 0.132 / 0.173 s | 1.57 s |
| model glue outside the blocks (patchify, embeddings, RoPE tables, final layers, the two shard transfers) | ~0.008 s | **~0.09 s** |

The remaining ~0.35 s of the 2.03 s interval is outside the forwards: the
sampler loop around them, the latent upsampler (now 0.03 s), the oracle
capture (0.05 s), the ComfyUI prompt turnaround, and the decode-behind
hand-off. Capturing the glue is worth at most 0.09 s and is no longer the
lever.

## What this means for 24 fps

The block region alone is 1.57 s per clip, against a 1.042 s budget for the
whole clip. No amount of work outside the blocks reaches the goal now. The
routes that remain, all exact by construction:

1. **Two clips in flight across the two shard cards from one scheduler
   thread.** The 21/27 split leaves one card idle while the other computes.
   A single issuing thread that interleaves clip A's xpu:0 segment with clip
   B's xpu:1 segment, with per-clip static buffers and event-ordered
   transfers, would bound the block region's throughput cost near 0.8 s per
   clip. This is not the retired two-thread design: no ComfyUI sampler runs
   on a worker, no shared registry, no capture concurrent with replay.
2. **The audio stream** (29% of every block, 26 tokens, 3.3x above its
   roofline) on the idle card concurrently with the video stream, and the
   proven bit-equal adaLN fused kernel (~0.05 s).
3. The smaller remaining items: glue capture (0.09 s), the oracle capture
   moved behind the pipeline (0.05 s), prompt turnaround.

Even 1 and 2 together land near 1.1–1.3 s per clip on the measured
numbers, so 24 fps is still not established as reachable; it is closer than
it was, and every step so far has kept all four outputs byte-identical.
