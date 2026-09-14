# Nonblocking stack profile selects a small-state residency candidate

One unchanged boat clip ran on PID24848 under a 15-second, 100 Hz py-spy 0.4.2
attachment. The profiler read Python stacks without pausing the process,
capturing locals or modifying the server. Existing ptrace restrictions required
local sudo for this read-only attachment; no security or power settings changed.

The request completed and all four output tensors matched baseline-01 exactly.
Preview readiness was 6.288 s. That is an instrumented diagnostic, not a new speed
record; use the 30-request uninstrumented distribution for performance claims.
The profiler reported 5,428 thread samples and 142 read errors. Each of four
Python threads had 1,357 recorded samples. The prompt worker had 816 queue-idle
samples and 541 non-queue-idle samples.

## Finding

Of the worker's non-idle samples, 120 stopped at `model_management.cast_to`'s
synchronous copy line 1568. Their full ancestry distinguishes:

| Call path | Recorded samples |
| --- | ---: |
| Gemma RMSNorm weight cast/copy | 79 |
| Gemma4 per-layer scalar cast/copy | 37 |
| Linear weight cast/copy | 4 |

Another 14 leaf samples stopped at the all-layer hidden-state CPU copy in
`sd1_clip.py:68`, supporting the earlier crop-before-copy candidate.

These are stack occupancies, not synchronized transfer or kernel durations.
A synchronous copy can wait for earlier GPU work; its sampled time is not all
removable overhead. Nonblocking reads can miss frames, so do not turn these
counts into a precise latency-savings prediction.

Source inspection explains why tiny state can still be on CPU despite most
encoder weights being resident. RMSNorm weights lack `comfy_cast_weights` and
can miss the final partial-loading budget. Parent-layer scalar buffers are
absent from the ordinary parameter-only load list. Both paths then explicitly
cast/copy their state to the input device during each forward.

Header-only inventory finds 289 text RMSNorm weights totaling 1,539,584 bytes,
plus 48 BF16 layer scalars totaling 96 bytes. Preserving roughly 1.47 MiB on the
encoder device could remove these repeated tiny transfer boundaries without
changing normalization or multiplication arithmetic. It requires correct
ownership, accounting and unload behavior; no loaded-state fix was made here.
The [small-state audit](encoder-small-state-audit.md) now supplies an opt-in
candidate and twelve passing CPU lifecycle tests. It remains inactive.

## Compiler decision

The [stock compile audit](compile-source-audit.md) rejects an immediate
whole-model compile request: that graph cannot expose the required numerical
options, compilation limits or intact guards. A tiny CPU test demonstrates
the issue: default BF16 fusion is deterministic but differs from eager in 6/6
cases; options preserving rounding match eager in 6/6. Those results justify a
future bounded block-level compiler experiment. The [actual LTX block CPU gate](ltx-block-compile-cpu.md)
subsequently passed both stage token counts with two compiled graphs and no
graph breaks. Neither test is an XPU exactness or speed claim.

## Evidence and retention

[Trace](../data/stack-profile-01/stacks.json),
[stack summary](../data/stack-profile-01/stack-summary.json),
[exact output gate](../data/stack-profile-01/parity.json),
[request profile](../data/stack-profile-01/request/profile.json),
[profiler log](../data/stack-profile-01/profiler.log),
[deletion receipt](../data/stack-profile-01/retention-completed.json).

The verified diagnostic tensor archive and MP4 were deleted after retaining
hashes, metadata and the passing comparison. Original references remain intact.
No server restart or GPU fault occurred. Prior goal turn was progress: it
established 30 exact requests and retention. This turn adds a measured source
bottleneck and a compiler numerical gate; the subsecond goal remains unmet.
