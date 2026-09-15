# First exact speedup: per-block XPU graph capture cuts the sampler 1.83x

September14, 2026. Packet19 (`prepared-encoder-graph-capture-19`, manifest
`e378498bb183982c59a76c366efc8d9e39f0197c747fb01e176299ab05ae84c7`), server
`encoder-server-graph-capture-19`, PID22639, boot `64bbd5d2`. Ten clips,
schedule original x2, graph x5, restored, original x2. **All ten matched their
original references bytewise on all four raw outputs.**

## Result

| Measure | Control (n=3) | Graph replay (n=4) | Effect |
| --- | ---: | ---: | ---: |
| Sampler 344+368 | 3.669 s mean | **2.001 s** median | **1.83x, −1.668 s** |
| Preview ready | 6.459 s mean | **4.792 s** median | **1.35x, −1.668 s** |
| Text encode 364 | 1.731 s | 1.752 s | unchanged |
| Video decode 374 | 0.619 s | 0.626 s | unchanged |

Control sampler values 3.590 / 3.704 / 3.713 s bracket the graph arm on both
sides, and the whole saving lands in the sampler, exactly where the
[dispatch-bound diagnosis](dispatch-bound-diagnosis-01.md) predicted it. The
3.2% drift between the bracketing controls is far smaller than the effect.

This is the **first speed win of this campaign, and it is lossless**: the
checkpoint, precision, resolution, frame count, sampler, step schedule and every
original graph are untouched, and the four raw output oracles pass on every clip.

## Why it is bit-exact

Replaying a captured graph re-executes the recorded command list: the same
kernels, in the same order, over the same memory. Nothing is recompiled, fused,
reordered or re-tiled. The adapter additionally proves it per graph, at capture
time, before the graph is ever used:

- a fresh eager execution of the same block on the same input bits is compared
  to the replayed result as raw `int16`, including signed zero; any difference
  refuses graph mode outright;
- the graph is proven **non-inert** by perturbing its static input and requiring
  the replayed output to move, so an empty capture cannot masquerade as a pass.

96 graphs were captured (48 blocks x 2 sampler stage shapes), replayed 2,640
times across the arm, with 18 mirrored tensors per block and every block's
output landing back in its own input buffer.

## Cost and shape

The first graph clip costs **11.469 s** instead of 6.35 s: capture, warm-up and
the per-graph eager proof are paid once per process per stage shape. Device
memory after the whole arm is 20.60 GiB on XPU0 and 19.45 GiB on XPU1, against
the ~20 GiB of resident transformer weights, so the 96 graph pools are modest.
Restoring the original routes returns the sampler to 5.099 s on the first
request and 3.704 / 3.713 s after, confirming the routes came back cleanly.

## What the five failed packets taught

Packets 14 through 18 each failed on a real defect that the adapter's guards
refused rather than silently absorbing. Every one is now a CPU test (29 pass):

| Packet | Refusal | Cause |
| --- | --- | --- |
| 14 | `cannot describe ... at arg` | `CompressedTimestep` and `GuideAttentionMask` declare `__slots__`, so a `__dict__`-only walk cannot see their tensors |
| 15 | `cannot describe builtins.function at transformer_options['callbacks'][...]` | the runtime options bag carries the sampler's own callbacks, wrappers and route registry |
| 16 | `attribute '__weakref__' of 'UUID' objects is not writable` | `uuid.UUID` lists `__weakref__` in `__slots__`; rebuilding tensorless objects is pointless and fragile |
| 17 | `'NoneType' object has no attribute 'get'` | `_invoke` rebuilt the keyword list and dropped `transformer_options` |
| 18 | 339 graphs, then `shard is not fully resident on xpu:1: {'cpu'}` | the signature included the shard's per-forward `_move` cache, whose keys are object ids; only the secondary device copies, so its 27 blocks re-captured every step until memory pressure evicted the model |

Packet18's failure is the instructive one. The signature churn was invisible on
XPU0 (21 blocks, 2 signatures each, correct) and total on XPU1 (27 blocks, 11
signatures each). A `MAX_SIGNATURES_PER_BLOCK` guard now turns that class of
runaway into an immediate, named error instead of an out-of-memory eviction.

A separate trap, found offline before any packet: `torch.xpu.graph` caches one
class-level capture stream bound to the first device it sees, so capturing on a
second device records an **empty** graph and emits only a `UserWarning`. It first
showed up as a fake 5.612x speedup with bit-equality False. Every capture now
passes an explicit per-device stream and proves non-emptiness.

## Where the remaining sampler time is

2.001 s over 11 steps is 182 ms/step. The offline probe replayed 48
LTX-shaped blocks in 104 ms, so roughly 78 ms/step is still Python: the
per-block static fill copies 18 tensors x 48 blocks = 864 tensors per step, and
16 of those 18 are identical for every block within one forward. Sharing one
static buffer set per device per forward should remove most of it. The
patchify, embedding and final-layer work outside the 48 blocks also stays eager.

## Scope and limitations

One process, one boat fixture, four warm graph clips against three warm
controls. Capture cost is excluded from the warm medians and reported
separately. Only the transformer blocks are captured. This is not yet a
full-suite or sustained-streaming claim, and the one-second north star is
not reached: the clip is 4.79 s for 1.042 s of video.

Evidence: [`data/graph-capture-19-result.json`](../data/graph-capture-19-result.json),
per-clip summaries and the restore receipt under [`data/graph-capture-19/`](../data/graph-capture-19/),
mechanism validation in [`data/xpugraph-validation-01.json`](../data/xpugraph-validation-01.json).
