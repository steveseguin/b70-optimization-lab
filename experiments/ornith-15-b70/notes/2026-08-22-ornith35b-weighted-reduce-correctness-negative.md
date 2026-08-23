# Ornith 1.5 35B-A3B: weighted routed-expert reduction

Date: 2026-08-22 EDT

Status: **CLOSED CORRECTNESS NEGATIVE — keep weighted multiplication separate**

The accepted MoE optimization leaves the routed-expert weighting as a stock
`MUL`, then replaces seven serial additions with one ordered reduction kernel.
This follow-up attempted to absorb the weighting into that reduction. It would
remove another 40 launches/token and avoid about 5 MiB/token of temporary FP32
traffic.

The candidate matched only the exact Ornith `[2048,8]` weighted tensor and the
already-validated eight-expert reduction chain. Each per-expert multiplication
was assigned to a volatile FP32 temporary before the products were added in the
same expert order. The door fired 5,080 times in a forced 128-token run, or 40
times per evaluated token after the initial graph setup.

The same-binary, fixed-seed, temperature-zero comparison failed before any
performance screen:

| Arm | Output SHA-256 |
| --- | --- |
| accepted stack | `c6fe7cb03197eb3bb04c65ee6558f1f908f5da08cb6eb15166ab724d49fd427f` |
| fused weighting candidate | `e37dbe4d92e5e5a268389da87ef19cbf1ba0f7f8b30901a4c501220e931450f4` |

The hidden reasoning text diverged within its first generated paragraph. Do not
time or promote this candidate: a volatile private product does not reproduce
the graph-visible stock `MUL` closely enough for this model. The exact rejected
source is archived as
`../patches/llamacpp-ornith15-weighted-reduce-correctness-negative-20260822.patch`.
The published package remains unchanged.
