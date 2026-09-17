# Packet 72: batching two clips is closed — a batch-2 forward differs even for identical rows

*2026-09-17 06:21–06:23 UTC, server PID 86546. Evidence
`data/graph-capture-72/` and `encoder-server-graph-capture-72/concurrent-cfg-f72-proof-01.json`.
Warm clip exact; the proof clips themselves exact (the wrapper returns the
batch-1 result).*

Lockstep variant: the second row differs only in latent and conditioning;
timesteps, option sigmas and everything else are identical across the two
rows. Plus a control where both rows are the same input.

| Comparison (11 forwards) | bitwise equal | max abs diff |
| --- | ---: | ---: |
| stacked row 0 vs its batch-1 forward | 0 / 11 | 1.40 |
| stacked row 1 vs its batch-1 forward | 0 / 11 | 1.22 |
| **identical-rows control**, `cat(x, x)` row 0 vs batch-1 | **0 / 11** | up to **0.98** |
| identical-rows control, row 1 vs batch-1 | 0 / 11 | up to 0.98 |

With two copies of the same input, a batch-2 forward should be two copies of
the batch-1 output under any row-independent computation, and it is not, by
amounts that are not rounding. Something in this forward path is
batch-dependent (LTX's per-frame timestep compression, the audio–video cross
attention, or the lab's capture route at batch 2 are the candidates), and
none of those admits a bit-exact two-clip batch. Under the lossless rule the
batching route is closed; it is recorded, not pursued.

## What remains toward 24 fps

Per distinct clip: 2.03 s standing, of which the captured block region is
1.57 s. The exact levers left, in order of size:

1. **Single-scheduler two-clip sampler** (design B in
   [two-clip-sampler-design](two-clip-sampler-design.md)): two clips, one
   issuing thread, both shard cards busy. Expected near 1.2 s per clip.
   Large build; its first piece is a CPU-provable two-clip step loop.
2. Model glue capture (0.09 s), oracle capture behind the pipeline (0.05 s),
   the proven adaLN fusion (0.05 s): about 0.2 s together.
3. Block kernel work on the launch-bound audio stream.

Even 1 and 2 together leave the clip above the 1.042 s budget on the
measured numbers; 24 fps at 256x256 with bit-exact output is not established
as reachable on this hardware, and every step so far has kept all four
outputs byte-identical.
