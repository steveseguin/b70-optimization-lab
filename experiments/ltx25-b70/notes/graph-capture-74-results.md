# Packet 74: two clips in flight across the shard cards, 2.03 → 1.61 s per distinct clip, exact; the text encoder is now the wall

*2026-09-17 13:03–13:07 UTC, server PID 4280 (this boot's single server,
kept running). Evidence: [`data/graph-capture-74/`](../data/graph-capture-74/),
committed per arm. Ten distinct prompt/seed fixtures, every emitted clip
compared with its own reference.*

| Arm | Prompts | Distinct | Exact | Steady interval | min | p95 | fps equiv |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| **`pipe-samp2`** (two sampler workers, per-clip streams, staged cross-card moves, capture lock, fast path, save-behind) | 24 | 21 (+3 fills) | **21/21** | **1.607 s** | 1.05 s | 2.81 s | **15.6** |
| `pipe-fast-save` (control) | 12 | 11 | 11/11 | 2.045 s | | | 12.2 |

The warm clip's oracle reported "failed" only because a single prompt is
now a pipeline fill and emits placeholders (index -1); the driver skips
fills, and every real clip matched.

## What the two-clip sampler does

Two worker threads each own one clip. Each thread issues on its own stream
on each shard card and stages the cross-card activation through pinned host
memory (probe 5: the driver's peer copy and shared default streams were what
serialised the cards). Captures are exclusive under a reader-writer lock and
wait for the device to drain; replays are shared. Nothing is cached or
shared between clips: each clip has its own static buffers and graphs, its
own noise (generation serialised), its own conditioning. The oracle checked
all 21 clips against references made by the original single-card recipe.

Per-clip sampler wall with two in flight: 2.4–2.5 s, i.e. about 1.2 s per
clip of sampler throughput, against 1.67 s alone.

## The new wall

Intervals cluster at 1.05–1.6 s with three spikes near 2.8 s. The text
encoder runs once per clip on one card at 1.59 s (fp32 by upstream design),
which caps the stream at 1/1.59 s = 15.7 fps; the measured 15.6 fps sits on
that cap, and the spikes are the samplers waiting for conditioning. The
sampler is no longer the binding stage.

## Next lever

Run the encoder two prompts deep across two cards. A second full replica
does not fit beside the VAEs (26 GB weights plus ~3 GB activations on a card
holding 3.5 GB), so it must be the encoder's 48 layers sharded across xpu:2
and xpu:3 with two encode workers, the same construction as the sampler.
Expected: encode throughput 1.59 → ~0.8 s per clip, stream then sampler-bound
near 1.2 s per clip (~20 fps). After that, rebalancing the transformer split
toward 24/24 (memory permitting) and the block-level kernel work.

This needs a new packet, hence a server restart, which on this kernel has
preceded lockups; the user decides when.
