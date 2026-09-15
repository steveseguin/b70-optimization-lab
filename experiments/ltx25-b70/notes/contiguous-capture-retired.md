# Contiguous per-device block capture, retired on measurement

*2026-09-15, packet33 server (`encoder-server-graph-capture-33b`), 3 graph clips
then the restore-time timing pass.*

## The idea

With per-block graphs the sampler still pays, for each of the 48 blocks on each
forward, a Python route call that re-moves eighteen arguments
(`ltx_layer_shard._BlockRoute.__call__`), a dictionary rebuild and a replay
launch. `av_model`'s loop threads only `(vx, ax)` between blocks -- every other
argument it passes is loop-invariant -- so a run of consecutive blocks on one
device is legally one graph. Blocks 0-20 live on xpu:0 and 21-47 on xpu:1, so
48 graphs could become 2, removing 46 route calls per forward.

The transformation was built and its run-splitting verified offline against the
real 21/27 layout: coverage, consecutiveness, one device per run, no run
crossing the block that returns state to the primary device, at chain lengths
1, 4, 8, 21 and 48. chain=48 yields exactly `[(0,20), (21,47)]`.

## Why it is worth nothing

`measure()` replays every captured graph back-to-back with a host sync, which is
pure GPU time with no Python in between. Two shapes are captured per block, one
per sampler stage:

| Stage | Blocks | Sum of replays |
| --- | ---: | ---: |
| 64 video tokens | 48 | **131.8 ms** per forward |
| 256 video tokens | 48 | **172.7 ms** per forward |

The clip runs **11 forwards** (1584 replays over three clips, 48 blocks each).
So the blocks' own GPU time is between 11 x 131.8 = **1.45 s** (every forward at
the cheap stage) and 11 x 172.7 = **1.90 s**, against a measured block region of
about **1.58 s** of a 1.943 s sampler.

**The GPU is already busy for essentially the whole block region.** The per-block
Python is overlapped with the previous block's 2.7-3.6 ms of kernels and costs
no wall time. The ceiling on removing all 46 route calls is at most ~130 ms, and
realistically zero.

This is the opposite of the pre-graph situation. The
[dispatch-bound diagnosis](dispatch-bound-diagnosis-01.md) found roughly three
quarters of sampler time was issue overhead; graph capture already took that,
and what is left in the block region is kernel execution.

## What this retires and what it leaves

Retired: contiguous/whole-shard capture, and with it the last "remove Python
from the sampler" idea. The chain machinery is kept (verified, defaulting to the
per-block behaviour, one arm `graph-c48` available) but no packet is spent
tuning it.

Not retired, and now clearly the two real targets:

- **The audio stream, 0.43 s/clip.** Restore-time attribution on real blocks,
  by the model's own `run_ax` switch: at 256 video tokens block0 costs 3.578 ms
  and 2.690 ms without the audio stream, so audio is **0.888 ms, 24.8%**; at 64
  tokens it is 0.782 ms of 2.698 ms, **29.0%**. The cost barely moves with video
  token count because the audio stream is small and latency-bound, and it runs
  about 3.15x above its own weight-read roofline. The two cross-attentions are
  0.30 ms each.
- **Text encoding, 1.81 s/clip**, which is larger than either sampler stage and
  is the subject of the next packet.
