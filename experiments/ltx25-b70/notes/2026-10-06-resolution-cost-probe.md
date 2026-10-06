# What a larger picture costs: decoder measured, transformer estimated (2026-10-06)

Owner's question: what would 640x360 do to the frame rate? The pipeline needs multiples of 64, so the sizes
probed are 256x256 (today), 512x320 and 640x384 (640x360 after a crop). Script
`scripts/probe-resolution-cost.py` (written by Codex), one card, eager, 12 transformer blocks, the real VAEs in
bf16, seeded random latents. Result file `data/resolution-cost/resolution-cost-01.json`.

## Decoder: measured

| Output size | Pixels vs 256x256 | Video decode, one card | vs 256x256 | Peak device memory |
| --- | ---: | ---: | ---: | ---: |
| 256x256 | 1.0x | 0.52 s | 1.0x | 2.6 GiB |
| 512x320 | 2.5x | 1.17 s | 2.26x | 3.1 GiB |
| 640x384 | 3.75x | 1.66 s | 3.2x | 3.5 GiB |

Audio decode is 0.19 s at every size. These are eager timings; the server replays a captured decode graph,
which is somewhat faster, but the ratios are what matter: decode grows almost in step with the pixel count.

## Transformer: not measurable this way

Eager block time came out at 8.1-8.6 ms per block at every token count (64 to 960), because in eager mode
the GPU work hides under Python dispatch, and the busy counter counts the context as active between kernels.
The server replays graphs, where September's measurement gave 2.74 ms per block at 64 tokens and 3.61 ms at
256. Extrapolating that slope (about 4.5 us per token per block) to 240 and 960 tokens gives roughly 1.5 times
today's sampler cost per clip for 640x384. Attention grows faster than linearly, so this may be low. A real
number needs a server run at that size (a packet variant with speed-only arms).

## What it adds up to (estimate)

Per clip at 640x384: sampler about 1.5x today's (estimate), decode about 3.2x today's (measured), text encoder
unchanged. With today's split (about 2.1 / 0.65 / 0.45 GPU-seconds), that is roughly 3.2 + 2.1 + 0.45 =
about 5.7 GPU-seconds per clip against about 3.0 now, so roughly half today's frame rate: about 13-16 fps on
this machine, around 20 fps with two more cards taking decode. The decoder becomes the biggest single cost,
so at larger sizes decode optimisation (graph capture is already in; tiling, bf16 already) matters most.
