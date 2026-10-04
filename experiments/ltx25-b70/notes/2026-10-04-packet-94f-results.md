# Packet 94f: spreading the sampler's blocks over three or four cards is exact but not faster with two clips in flight (2026-10-04)

Three servers from `prepared-encoder-shard4-94f` (manifest `6638e7fa...`), one
per layout, on kernel 7.0.0-39 (first boot on it), GuC 70.44.1, memory blocks
53-57 offline, `LTX_BUSY_WINDOWS=0`. Runner `scripts/run-campaign-94f.sh
<mode>`; receipts in `data/shard4-94f/<mode>/`. Each server: text-window
probe, serial capture pass, decode probe, freeze, post-freeze self-check,
placement probe (ten fixtures), timed arm. All clips verified against the
`stability-01-w93c-*` references. No GPU fault, no lockup, every server
stopped cleanly.

| Layout (blocks on xpu:0/1/2/3) | Probe | Timed clips exact | Interval mean | Sampler job median | Compute-engine s per clip: xpu:0 / 1 / 2 / 3 | Total |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| control, two-way (23/25/0/0) | 10/10 | 36/36 | **1.41 s** | 2.59 s | 1.24 / 1.32 / 0.42 / 0.87 | 3.85 |
| shard3-c (20/20/8/0) | 10/10 | 76/76 | 1.47 s | 2.81 s | 1.30 / 1.27 / 0.83 / 0.84 | 4.24 |
| shard4-a (18/18/8/4) | 10/10 | 76/76 | 1.50 s | 2.88 s | 1.34 / 1.20 / 0.85 / 1.02 | 4.41 |

## Reading

1. **Block placement is exact.** Transformer blocks give the same bytes on
   xpu:2 and xpu:3 as on xpu:0 and xpu:1: 172 of 172 clips across the two
   spread layouts, plus the probes. The mechanism (named layouts, serial
   capture pass, freeze, no load after the freeze) works.
2. **It is not faster, and slightly slower.** The stream went from 1.41 to
   1.47 and 1.50 s per clip, the sampler job from 2.59 to 2.81 and 2.88 s,
   and the total compute-engine time per clip rose by 0.4-0.6 s. The
   prediction (busiest card down to about 1.05 s) was wrong: xpu:0 did not
   get less busy when blocks left it.
3. **Why.** One clip's sampler work is a serial chain: every block waits for
   the one before it, on whichever card it lives. Moving blocks to another
   card does not shorten the chain; it adds a card boundary (a staged copy
   through host memory and a wait) to every one of the eleven forwards. With
   two clips in flight on two cards the clips already almost never collide
   (1-5 % overlap, packet 90c), so there was no contention to relieve.
   Throughput is clips in flight divided by the chain time: 2 / 2.6-2.9 s.
4. **What the spread layouts are good for is more clips in flight.** With
   blocks on four cards, three or four clips can each be on a different card
   at once. The cards, not the chain, then set the limit: about 0.31 s of
   fixed work plus 18 blocks x 11 forwards x 0.04 s on each of xpu:0 and
   xpu:1 is about 1.05 s per clip (a projection). That needs a third (and
   fourth) sampler worker, each with its own graph pools on every card.
5. The compute-engine busy counter rises with more boundaries although the
   kernels are the same; it probably includes time a context holds the
   engine while waiting on a copy. Treat it as an upper bound on compute.

## Host

First hour of sustained GPU load on kernel 7.0.0-39: zero `hard LOCKUP`
lines, against five in about two and a half hours of load on 7.0.0-38. Not
yet enough to call it fixed.

## Next

Packet 95: three and four sampler workers on the shard4-a and shard3-c
layouts (and three on two-way as a reference), same exactness gates, with
memory accounted per worker per card. Decode capacity (two workers, about
0.9-1.0 s per clip) becomes the next limit if the sampler reaches 1.05 s.
