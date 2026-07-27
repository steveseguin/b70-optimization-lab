# FP8 KV decode component attribution

Date: 2026-07-27 America/Toronto

Status: diagnostic. No FP8 throughput result is promoted because the graph
arms used for endpoint timing failed within-FP8 exactness.

## Result

The expected bandwidth win is not present in the current Xe2 kernel path.
FP8 halves the stored KV bytes, but the paged-attention kernel pays
descale/conversion cost and was slower than BF16 at every matched shape tested.
The cache-write conversion itself is negligible.

The structured measurements are in
[`decode-component-attribution-20260727.json`](../data/decode-component-attribution-20260727.json).

## Cache insertion

The direct `reshape_and_cache_flash` test used the real target shape:
`T=12`, `Hkv=2`, `D=128`, block size 64, 512 blocks, BF16 input, and static
scales on B70 card 0.

| cache dtype | median per layer | projected 48-layer pass |
|---|---:|---:|
| BF16 | 6.327 us | 303.675 us |
| FP8 | 6.454 us | 309.778 us |

FP8 adds only about 6.1 microseconds across a projected 48-layer target pass.
Fusing or rewriting cache insertion cannot explain, or recover, the endpoint
gap.

## Paged attention

The matched direct FlashAttention test used query width 12, two KV heads,
head size 128, block size 64, a BF16 query, and static FP8 K/V descales.

| query heads | context | BF16 cache | FP8 cache |
|---:|---:|---:|---:|
| 12 | 128 | 19.566 us | 21.358 us |
| 12 | 512 | 19.267 us | 21.394 us |
| 12 | 1024 | 24.556 us | 33.613 us |
| 12 | 4096 | 24.879 us | 29.630 us |
| 18 | 128 | 19.549 us | 21.586 us |
| 18 | 512 | 19.478 us | 21.528 us |
| 18 | 1024 | 24.850 us | 34.574 us |
| 18 | 4096 | 38.689 us | 52.781 us |

This is a single-card component test, not an endpoint claim and not compiled
graph timing. It nevertheless rejects the premise that lower FP8 KV bytes
automatically make the current Intel attention implementation faster.

## Endpoint decomposition

The rejected no-prebuilt FP8 graph arm measured 94.129464 tok/s versus the
sealed BF16 record's conventionally counted 101.941721 tok/s. Speculation
accounts for only part of the difference:

| row | emitted/cycle | inferred cycle time |
|---|---:|---:|
| sealed BF16 record | 3.950280 | 38.750 ms |
| FP8 no-prebuilt graph, rejected | 3.887613 | 41.301 ms |
| FP8 M-wide graph, rejected | 3.770809 | 41.815 ms |

For the closest FP8 arm, emitted tokens per cycle fell 1.59%, while inferred
cycle time grew 6.58%. Together they explain the 7.66% endpoint loss. The
timing is diagnostic only because that arm was 12/13 exact.

## Decision

1. Do not spend an experiment on cache insertion; its measured ceiling is too
   small.
2. Localize and fix graph/M-wide nondeterminism before accepting any speed
   result.
3. Once graph execution is exact, profile the approximately 2.55 ms per-cycle
   gap rather than attributing it all to KV traffic.
4. Keep FP8 paged attention as a kernel target, with long-context shapes
   especially relevant to the later prefill/long-context phase.

The general lesson for future models is that capacity, bandwidth volume, and
kernel throughput are separate claims. A compressed cache is a capacity win
immediately; it becomes a decode-rate win only when the backend consumes the
compressed representation efficiently.
