# Every GPU buffer was also costing its size in host RAM (four-card processes)

October 4, 2026. Kernel 7.0.0-39, xe driver, compute-runtime 26.18.38308.1, Level Zero loader 1.28.2.

## What happened

Packet 95 with three sampler workers on the four-card layout ran the host out of RAM and the kernel killed the
server (18:03–18:18 UTC, no GPU fault). The two-clip control on the same packet then ran clean, but a memory
sampler showed about 95 GiB of the host's 115.6 GiB gone while the server was up, with only ~8.5 GiB in the
process's own memory and almost nothing in page cache.

## What it is

In a process that has more than one card open, the GPU runtime does two things to every device buffer:

1. It shares the buffer with every other card (a dma-buf export, imported on each peer). Unified Runtime asks
   for this at allocation time so that card-to-card copies can go directly between cards.
2. With the runtime's default "deferred backing" on this GPU family, the buffer ends up holding system-memory
   pages of its own size as well as its video memory. The kernel counts them as `GPUActive` in `/proc/meminfo`.
   They are not in the process's RSS, not page cache and not slab, which is why they looked "unaccounted".

So host RAM, not video memory, was the limit: the server can use at most about 100 GiB of its 128 GiB of video
memory before the host runs out.

Evidence from the live two-clip server (18:55 UTC, `shard4-a`, two workers):

| | card 23 | card 27 | card 43 | card 47 |
| --- | ---: | ---: | ---: | ---: |
| video memory in use (GB) | 26.1 | 21.7 | 30.0 | 22.6 |
| imports from the other cards, "gtt" (GB) | 74.1 | 78.4 | 70.3 | 77.7 |

- Each card's "gtt" figure equals the other three cards' video memory added together. It is bookkeeping for
  the imports, not buffers living in system RAM.
- `GPUActive` 92.6 GiB, `MemAvailable` 16 GiB, swap full, 4,107 shared buffers totalling 98.9 GB.
- Speed is not affected: the buffers the cards compute on are in video memory (see the probe).

The earlier single-card probe (`probe-vram-host-shadow.py`) missed this because a one-card process has no
peers to share with.

## Probe

`scripts/probe-multicard-buffer-sharing.py` (all four cards visible, no server running) creates a 4 GiB weight
on one card, runs a trivial kernel on the others, creates a second weight, and copies the first across cards.
Columns are after the cross-card copy, 12 GiB of device buffers alive.

| setting | host RAM held by the GPU driver | imports on other cards | matrix-vector speed | results |
| --- | ---: | --- | ---: | --- |
| default | 12.6 GiB | yes, at allocation | 603 GB/s | reference |
| `SYCL_UR_USE_LEVEL_ZERO_V2=0 UR_L0_USM_RESIDENT=0x1` | 4.1 GiB | only for the copied buffer | 603 GB/s | identical |
| `NEOReadDebugKeys=1 ForceZeDeviceCanAccessPerReturnValue=0` | 0.3 GiB | none | 603 GB/s | identical |
| `NEOReadDebugKeys=1 EnableDeferBacking=0` | 0.3 GiB | yes | 603 GB/s | identical |

`EnableDeferBacking=0` is the smallest change: buffers are still shared, so card-to-card copies stay direct,
and only the host-memory copy goes away. It changes where memory is placed and nothing about the arithmetic.
`ForceZeDeviceCanAccessPerReturnValue=0` also removes the sharing; card-to-card copies would then go through
host memory, which may be slower. It is the fallback if the first setting misbehaves in the server.

## Packet 95 results so far (default settings)

All against the `stability-01-w93c-*` references.

| layout, workers | probe exact | timed exact | seconds per clip (mean) | note |
| --- | ---: | ---: | ---: | --- |
| two cards, 2 | 10/10 | 116/116 | 1.413 | control |
| four cards (18/18/8/4), 2 | 10/10 | 116/116 | 1.518 | |
| four cards (18/18/8/4), 3 | – | – | – | host out of memory during capture |

## Server runs with the setting (runner 95b)

Same packet, server launched with `NEOReadDebugKeys=1 EnableDeferBacking=0`; the runner refuses to start
without both and stores them in `data/workers-95b/<mode>/runtime-environment.txt`. Results are appended below
as the combinations finish.

| layout, workers | probe exact | timed exact | seconds per clip (mean / median) | compute seconds per clip, cards 0-3 | host RAM held by the GPU driver (peak) | lowest `MemAvailable` |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| four cards (18/18/8/4), 3 | 10/10 | 115/115 | 1.387 / 1.489 | 1.273 / 1.245 / 0.847 / 1.085 | 3.6 GiB | 43.7 GiB (during model load, host copies of the weights) |
| two cards, 2 (control) | 10/10 | 116/116 | **1.358** / 1.641 | 1.231 / 1.297 / 0.380 / 0.835 | 3.6 GiB | as above |
| three cards (20/20/8), 3 | 10/10 | 115/115 | 1.470 / 1.411 | 1.328 / 1.367 / 0.861 / 1.046 | 3.7 GiB | as above |

Three workers fit and are exact. Peak video memory per card: 27.3 / 24.0 / 29.3 / 23.3 GiB. The sampler's
chain time grew from 2.94 s (two in flight) to 4.12 s (three in flight), so the cards are saturated: more clips
in flight no longer buys much. What limits speed now is compute per clip on the busiest card (1.27 s on card 0).

The two-clip control is the like-for-like comparison of the setting: 1.413 s per clip by default, 1.358 s with
it (one run each; this lane has seen a few percent of drift between runs, so read it as "not slower", with a
likely small gain from the host no longer swapping and no longer squeezing the page cache). With two clips in
flight the clips finish in pairs, which is why the median interval (1.641) sits above the mean; the mean is the
throughput.

Four workers on the four-card layout were tried later (20:42 UTC): the runner's video-memory check stopped
the run cleanly before the fourth worker captured (exit 18, server stopped normally). With three workers the
cards already hold 26.6 / 20.2 / 29.0 / 19.6 GiB of their 32. So with the host-RAM limit gone, video memory on
the card that carries half the text encoder plus eight transformer blocks is the next ceiling for clips in
flight. The 20/20/8 layout with three workers was run at 21:20 UTC (row in the table: exact, 1.470 s per clip,
slower than both other layouts, with a 4.2 s sampler chain). Two cards with three workers was not run (it does
not fit video memory by the 94f figures). Index base 255000 is unused; 257000 (four cards, four workers) is
used up to its capture pass.

One operational trap, recorded so it is not repeated: an offline test imported packet 95's source tree without
`python -B` and left 315 `__pycache__` files inside the sealed packet. The launcher refuses a packet with files
that are not in its manifest ("Uninventoried packet files"), so two launches at 19:57 and 20:32 UTC never
started a server; the runner waited out its 30-minute health timeout. Nothing ran and no clip index was used.
The cache files were removed (only those) and the packet's gate passes again. Rule: anything that imports
from a `prepared-*` directory runs with `-B`.
