# The goal is not arithmetically excluded: the floor is 0.861 s, the clip is 1.042 s

September15, 2026. Offline, exclusive GPUs. This note replaces guesswork about
whether 24 fps is reachable losslessly with a measured budget.

## The arithmetic

The transformer checkpoint is 42.02 GB of BF16 weights and the sampler runs 11
steps, so a clip reads **462.2 GB**. One B70's measured device copy roofline is
**537 GB/s**, giving a weight-read floor of **0.861 s per clip**.

The clip contains **1.042 s of video** (25 frames at 24 fps).

**0.861 < 1.042.** At roofline the sampler alone would deliver **29 fps**. So the
north star is not excluded by the hardware; it needs the sampler at or under
1.042 s, with decode pipelined off the critical path.

| | Value |
| --- | ---: |
| Weight-read floor | 0.861 s |
| Measured sampler today | 1.942 s (**2.26x above floor**) |
| fps now, sampler + decode serial | 10.0 |
| fps if decode were pipelined | 12.9 |
| fps at the floor | **29.0** |
| Target | 24 |

## Where the 2.26x lives

Skip-differencing a graph-replayed 48-block chain (102.8 ms, 1.49x above its own
roofline). Each row is the chain's cost minus the cost with that component
disabled:

| Component | Time | Share |
| --- | ---: | ---: |
| Projections (q/k/v/out, at roofline) | ~48.5 ms | ~47% |
| Feed-forward | 32.06 ms | 31.2% |
| **RoPE elementwise** | 13.71 ms | **13.3%** |
| Attention gate (sigmoid + multiply) | 5.04 ms | 4.9% |
| **Scaled dot-product attention** | **3.29 ms** | **3.2%** |
| Norms + ada modulation | 2.16 ms | 2.1% |

Three results worth stating plainly:

- **Attention math is 3.2%.** The attention path is expensive because of its
  projections and elementwise work, not its attention.
- **Norms are 2.1%.** Fusing the normalisation and modulation chain, an obvious
  idea, is worth essentially nothing.
- **RoPE is 13.3%, four times all the norms together.** Caveat: the probe models
  RoPE as a `cat` of two scaled halves, while the shipped model calls a fused
  custom op (`comfy.quant_ops.ck.apply_rope_split_half1`). So 13.3% is an upper
  bound on the opportunity, not a measurement of the real path. Checking the real
  cost is cheap and worth doing before acting on it.

The chain is 1.49x above its own roofline; the real sampler is 2.26x above the
real floor. The difference is Python orchestration (about 15%, measured earlier
at 84.9% of profiler samples waiting on the model call) plus the non-block part
of the forward and the two cross-device transfers per step.

## What this rules in and out

It rules **out** the two ideas that would have been next by intuition: fusing the
elementwise/normalisation chain (2.1%) and anything targeting attention math
(3.2%). It also confirms the
[column-parallel retirement](column-parallel-retired.md) was right for a second
reason: splitting a chain that is only 1.49x above roofline cannot pay for ~16
gathers per block.

It rules **in** a budget. To reach 24 fps the sampler must come down from 1.942 s
to about 1.04 s. No single remaining lever does that. The credible combination is:

1. remove the residual per-block Python (whole-device capture rather than
   per-block) -- worth roughly the 15% orchestration share;
2. pipeline decode onto XPU3 so it leaves the critical path entirely -- worth
   0.56 s on the continuous metric, and the reason Stage 3 matters;
3. recover part of the projection and elementwise inefficiency, for which fusing
   the separate q/k/v projections into one GEMM per attention is the obvious
   untested candidate, and is bitwise-testable.

Reaching the floor exactly is not plausible. Reaching 1.04 s is not obviously
impossible, and that is the first honest statement this lane can make about the
north star.

Evidence: [`data/sampler-ceiling-01.json`](../data/sampler-ceiling-01.json),
[`data/block-gpu-attribution-01.json`](../data/block-gpu-attribution-01.json),
probe `probe-block-gpu-attribution.py`.
