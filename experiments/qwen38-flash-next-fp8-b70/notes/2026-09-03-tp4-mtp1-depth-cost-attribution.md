# MTP1 depth cost: attribution (2026-09-03 late evening, A122-A127)

The certified lossless MTP1 line is 1.2x the MTP0 line at short context and
0.6x at 2K/4K. Per-step wall-clock hooks (`Q38_STEP_TIMING_LOG`: target
forward, sampler, drafter; `Q38_LAYER_TIMING_LOG`: GDN attention, QSA
attention, MoE, hyperconnection mix) and two offline timings locate it.

| measurement | one row (MTP0) | two rows (MTP1, three selectors) |
|---|---|---|
| eager step forward at 2K (A123 / A122) | `185 ms` | `265 ms` (drafter 10, sampler 1) |
| eager per-layer split at 2K (A125 / A124), per step | GDN 26, QSA 32, MoE 77, HC 74 ms | GDN 66, QSA 40, MoE 202 (74-283), HC 93 ms |
| full-decode-graph step at 2K (A78 rate / A127 hook) | `71 ms` | replay `144-255 ms`, mean `181`; drafter 2-28, sampler 1-5 |
| fused MoE kernel alone (offline, W13-N32 map, EP map) | `0.45 ms` per layer call | `0.70 ms` (M=4: 1.18) |
| XCCL all-reduce, four cards (offline) | `0.11 ms` per [1,N] call | `0.11 ms` per [2,N]; two [1,N] calls `0.20 ms` (async issue does not overlap) |

Readings:

- The drafter is not the cost (2-28 ms per step in the graph line, 10 ms
  eager). The two-row target forward is.
- The MoE kernel's second row costs about 12 ms per step across 48 layers,
  and the extra collectives of the row-wise all-reduce about 10 ms (96 more
  calls at 0.11 ms). Neither explains the 110 ms gap between the size-1 and
  size-2 graph replays at 2K, nor the replay's 144-255 ms spread.
- The in-server MoE sub-block at two rows (202 ms mean, 74-283 ms spread in
  eager) therefore carries cost that is neither its kernel nor its
  collectives; the same spread appears in the graph replay. Candidates that
  remain: the number of captured nodes in the size-2 graph (the serial GDN
  rows, row-wise all-reduces and row-wise norm loops add on the order of a
  thousand small nodes, and XPU graph replay may pay per node), and
  something in the MoE sub-block's host path at two tokens (expert-map
  alignment, routing) that the offline kernel timing does not exercise.
- Both the eager and the graph line prefill 64-token chunks 2-3x slower
  with MTP1 on than with MTP0 (5-7 s vs 1.8-2.7 s per chunk); the drafter's
  chunk prefill is 30-320 ms of that, so most of the difference is again in
  the target forward with MTP on.

Next experiments (each one 16-minute attempt on the A127 packet):
A129 drops the row-wise HC norm selector (the norm loops' nodes), A130 drops
the row-wise all-reduce selector; the replay time deltas price those node
groups. If the node count is the cost, the fix is to consolidate: the
sealed exact-recurrent GDN kernel (stage `runtime-mtp1-exact-ad25aa9-b70`,
bit-identical to the serial path per A85/A100) replaces 36 serial pairs
with one kernel each, and an M-invariant single-launch variance kernel can
replace the norm loops if it reproduces the M=1 torch reduction bit for bit.

Data: `../data/20260903-tp4-mtp1-a122-eager-step-timing-2k.json`,
`../data/20260903-tp4-mtp0-a123-eager-step-timing-2k.json`,
`../data/20260903-tp4-mtp1-a124-eager-layer-timing-2k.json`,
`../data/20260903-tp4-mtp1-a124-a125-layer-timing-m2-vs-m1-2k.json`,
`../data/20260903-tp4-mtp1-a127-graph-step-timing-2k.json`,
`../data/20260903-b70-triton-block-fp8-moe-m1-m2-m4-timing-w13n32.json`,
`../data/20260903-b70-tp4-xccl-allreduce-latency.json`.

## Subtraction runs and clocks (A129, A130; 2026-09-04 00:00-00:25)

| packet | selectors | size-2 replay at 2K (all ranks) | 2K rate |
|---|---|---|---|
| A127 | serial GDN, row-wise all-reduce, row-wise norm | mean `181 ms`, `144-255` | 7.71 |
| A129 | minus row-wise norm | mean `220 ms`, `126-301` | 7.09 |
| A130 | minus row-wise all-reduce | mean `186 ms`, `117-251` | 7.87 |

Neither flag group changes the replay time; the spread between steps and
between servers is larger than either. GPU clocks sampled at 1 Hz stayed at
2800 MHz on all four cards through the decode windows with no throttle
reason. The size-2 replay costs about 110 ms more than the size-1 replay
on the same line, the plain MTP1 screen (A81, no selectors) was no better,
and the offline pieces that can be timed alone (MoE kernel, all-reduce
latency) account for about 25 ms of it. What remains is the two-row cost
of the captured kernels themselves (QSA sparse attention and indexer at two
rows over 2K keys, the GDN decode kernel twice, the MoE at two tokens) and
the replay's per-node overhead on XPU, which the subtraction runs could not
separate because the nodes they removed are a small fraction of the graph.

Ranked next steps for the depth lever:

1. Per-kernel device timing of the size-2 versus size-1 step (an XPU
   profiler pass on the eager line at 2K with the three selectors, reading
   kernel durations only, not attributions: the profiler's own overhead is
   known to distort ~6x on B70 but kernel-to-kernel ratios survive).
2. Replace the Python serial verifier-row path with the sealed
   exact-recurrent GDN kernel stage (`runtime-mtp1-exact-ad25aa9-b70`),
   which A85/A100 showed bit-identical to it, removing ~250 captured nodes
   and one of the two GDN kernel launches per layer.
3. A two-row QSA sparse-attention profile: the split-K kernel uses the same
   tile and split counts for one and two rows, so its two-row cost should be
   near 2x; if the profiler shows more, the indexer (`qsa_mqa_paged`,
   `argsort`, `expand`) at two rows is the place to look.
4. Only then the norm: an M-invariant single-launch variance kernel that
   reproduces the one-row torch reduction bit for bit.
