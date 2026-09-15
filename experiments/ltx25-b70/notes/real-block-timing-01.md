# Measured: the blocks are 81.5% of the sampler, and their weight reads run at 61.5% of roofline

September15, 2026, packet29, server `encoder-server-graph-capture-29`. Every
captured graph replayed 20 times with a host sync, on the **real checkpoint
blocks** — not a synthetic stand-in. Four clips, all bytewise exact.

## The measurement

| | Value |
| --- | ---: |
| Stage 1 (64 video tokens) | 131.73 ms/step, 2.744 ms/block |
| Stage 2 (256 video tokens) | 173.07 ms/step, 3.606 ms/block |
| Blocks over the whole clip | **1.573 s** |
| Sampler | 1.929 s |
| **Blocks as a share of the sampler** | **81.5%** |
| Orchestration plus the non-block forward | 0.357 s (18.5%) |

## A correction to the previous note

[The lever ladder](sampler-ceiling-01.md) claimed blocks were 61% of the sampler
and that 39% was "not blocks", making whole-run graph capture the top lever. That
was derived by scaling a **synthetic** 48-block chain (102.8 ms) by the weight
ratio. The real block is 2.744 ms where the synthetic is 2.14 ms — the proxy was
**28% cheap**, and it understated the blocks.

Corrected: blocks are 81.5%, not 61%. **Extending capture to whole contiguous
runs is therefore worth far less than estimated** — the entire non-block share is
0.357 s and capture would only remove part of it. That lever drops down the
ladder. Measuring the real thing changed the plan, which is why it was worth a
packet.

## Where the block time actually goes

Stage 2 has four times the video tokens and identical weights, so the difference
isolates token-dependent work:

| | Value |
| --- | ---: |
| Block weight bytes per step | 38.94 GB |
| Roofline at 537 GB/s | 72.5 ms |
| Stage 1 measured | 131.7 ms (**1.82x** above) |
| Stage 2 measured | 173.1 ms (2.39x above) |
| Token-dependent work at 64 tokens | 13.8 ms |
| **Weight-bound remainder** | **118.0 ms → 330 GB/s → 61.5% of roofline** |

So the dominant inefficiency is **not** elementwise work, which the earlier
attribution already put at 2.1% for norms and 3.2% for attention math. It is that
the block's weight reads only reach 61.5% of the achievable rate.

That is consistent with what the block contains. Its large matrices hit roofline
in isolation — `ff.net.0.proj` at 545 GB/s, `attn.to_q` at 571 — but the block is
full of **small** projections, and an isolated audio q/k/v triple runs at
**186 GB/s**. Those small projections are only about 21% of the block's bytes but
take roughly 43% of its weight time.

## What this means for the goal

Lifting the weight-bound part from 61.5% to ~90% of roofline would save about
0.45 s, which is roughly the distance between missing and reaching 24 fps. But
the only lossless mechanism found for it is q/k/v fusion, and **only three of six
sites are bitwise exact**, covering 72 MB of the ~160 MB of small projections.
That is worth about 0.10-0.15 s, not 0.45 s.

Honest position after this measurement:

| Lever | Worth | Status |
| --- | ---: | --- |
| Fuse the three qualifying q/k/v sites | ~0.10 s | measured exact, not built |
| Graph-capture the video decoder | ~0.20 s | needs a persistent axis cache |
| Contiguous per-device capture | ~0.10 s | demoted by this measurement |
| Pipeline decode onto XPU3 | 0.56 s off the per-frame path | needs Stage 3 |

Sampler after the sampler-side levers: about **1.73 s against the 1.042 s** that
24 fps requires — still **1.66x short**, with no identified lossless lever for the
remainder. The residual is small-GEMM efficiency, and the fusions that would fix
it are not bitwise exact at the shapes that matter.

This is the measured practical limit the plan asks to be documented rather than
worked around by quietly lowering quality.

Evidence: [`data/real-block-timing-01.json`](../data/real-block-timing-01.json)
and the restore receipt under [`data/graph-capture-29/`](../data/graph-capture-29/).
