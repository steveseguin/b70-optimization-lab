# Replay benchmark on card 3 (2026-10-12 02:47–02:52 UTC): replay works and buys nothing

One half token of the real launch sequence (24 layers, 1,142 launches, the kernels and
shapes of packet 29's measured dispatch, synthetic weights, 4.77 GB on the card),
200 measured iterations per mode after 10 warm-ups, pinned to the reserved cores.
State after every iteration compared byte for byte between modes: 420 of 420 equal;
token-dependent values were changed every iteration through device data. Clean kernel
log. ([summary](summary.json))

| Mode | Wall per half token, median | Sum of GPU kernel time |
| --- | ---: | ---: |
| direct: 1,142 SYCL submissions, as the runtime does today | 19.82 ms | 19.52 ms |
| one recorded command graph, one submission per iteration | 19.86 ms | (not observable per kernel) |
| 24 recorded graphs, one per layer | 20.11 ms | |

Readings:

1. **A recorded SYCL command graph of our real kernels replays correctly on the B70**,
   including kernels with sub-groups and local memory; recording takes 7–27 ms; three
   whole-half recordings grew driver memory by 12 MB in total and 72 per-layer graphs by
   95 MB. No pool blow-up of the kind seen in the torch lane.
2. **It does not make the half token faster.** With a quiet, pinned issuing core the
   direct path already finishes 0.3 ms after the GPU does: the host keeps ahead of the
   card, and the card's time per kernel is the same whether the launches arrive one by
   one or as a list. The per-launch cost on the GPU (3–5 µs for the smallest kernels) is
   therefore dispatch cost inside the card's execution, not submission overhead.
3. **So the earlier 12–18 ms "host enqueue loop" was overlap, not loss**, except when the
   host was busy with other jobs. Replay stays available as protection against a busy
   host, not as a speed lever. The raw Level Zero list path was not built (no typed
   bindings for the current kernels) and is not worth building for speed.

Consequence for the plan: the token is GPU kernel time. What remains is kernels (fewer
and cheaper launches that keep every lane busy), the two-card pipeline with the draft
head, and the controller overhead of the pipeline.

The first K0 attempt was refused by the wrapper on this boot's old, already reviewed
fault lines ([evidence](../evidence/20261012-k0-refused-old-boot-fault-lines/README.md)).
