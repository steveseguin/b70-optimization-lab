# Packets 69–71: the batch-2 forward runs, and with a perturbed timestep its rows do not match

*2026-09-17 05:55–06:15 UTC, after the runtime-PM fix. Servers 69 (PID
78108), 70 (80319), 71 (83466); each stopped cleanly with one SIGINT and a
five-minute gap before the next launch. Evidence under
`data/graph-capture-69..71/`. The warm clip was exact on every server.*

| Packet | What stopped the proof | Fix |
| --- | --- | --- |
| 69 | the capture registry's cap of four argument shapes per device (batch-1 and batch-2 shapes for two stages need four) | cap raised to eight |
| 70 | the comparison assumed a tensor; the LTXAV model returns `[video, audio]` | per-component comparison |
| 71 | **ran to completion**: 11 forwards, 0 errors | — |

## Packet 71 verdict

With the second row's latent, conditioning **and timestep** perturbed, the
batch-2 forward's rows do not match the batch-1 results:

| | row 0 (unchanged inputs) | row 1 (perturbed inputs) |
| --- | --- | --- |
| bitwise equal to its batch-1 forward | 0 of 11 | 0 of 11 |
| max abs diff, video output | **2.2** | 0.94 |

A difference of 2.2 in the output is not accumulation-order noise (bf16 at
these magnitudes would differ by ~1e-2). Row 0's inputs were identical to
the batch-1 run, so something about row 1 changed row 0: a cross-row
interaction. The suspect is the timestep path, where LTX's per-frame
timestep compression and the ada-LN tables are reshaped over the batch. In
the pair sampler both clips would step at the same sigma, so packet 72 runs
the lockstep variant (only the latent and the conditioning differ) plus an
identical-rows control (`cat(x, x)`), which separates a batch-dependent
computation from a timestep interaction.

If the lockstep rows match bit for bit, the pair sampler proceeds. If they
do not, batching is closed under the lossless rule and the single-scheduler
two-clip sampler is the remaining route ([design](two-clip-sampler-design.md)).
