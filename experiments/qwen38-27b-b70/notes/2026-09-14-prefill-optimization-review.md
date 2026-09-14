# Bounded prefill optimization review

September 14, 2026. This source and evidence review accompanies a focused effort
to fill useful missing 512-token, one-user prefill measurements. It does not
establish a performance improvement or change a serving default.

The user requested a modest follow-up, not an exhaustive optimization campaign.
Two options were reviewed. Neither warranted a new endpoint patch within this
scope. The next diagnostic is one runtime-profiler trace on the available 4B
W4A16 two-card setup after its missing baseline measurements are captured. That
trace is planned work, not a completed result in this note.

## Direct-output allocation: keep the existing negative result

The existing FP16 linear custom op processes at most 32 rows per GEMM and
concatenates the results. The September 13 candidate allocated the final output
once and wrote identically sized GEMMs into slices, preserving the arithmetic
and the small-row decode branch.

Its operator checks and endpoint output comparisons passed. The endpoint screen
showed approximately +3.0% prefill throughput on 4B, +2.1% on 9B and neutral
27B results, without a meaningful decode change. It did not establish a
repeatable improvement sufficient for promotion. These are historical screen
results, not newly measured gains.

There is no new mechanism or evidence to justify repeating that candidate.
Preserve the frozen packet and its unchanged-default decision:

- [September 13 results and timing definitions](2026-09-13-short-prefill-results.md)
- [Original preregistration](2026-09-13-short-prefill-prereg.md)
- [Frozen summary](../data/2026-09-13-short-prefill/summary.json)
- [Direct-output operator probe](../probes/prefill-rowchunk-out-probe.py)

## Prefill-only CLASSPAD: reject before an endpoint patch

R293's existing CLASSPAD implementation can process more rows per FP16 GEMM
using measured, deterministic oneDNN rounding classes. It already improves
high-concurrency serving. A tempting hybrid would retain the existing
small-row path for single-user decode and select CLASSPAD for larger prefill
calls.

This is not a proven arithmetic-preserving replacement for CLASSPAD0. The R291
census explicitly excludes the single-row rounding class when choosing an
eligible canonical class. The hybrid would therefore change intermediate
rounding relative to the existing reference, and its prefill and decode would
use different classes. Global CLASSPAD qualification does not qualify that
hybrid. Changing intermediate bits does not by itself prove a quality loss,
but complete output equality and repeatability would need new evidence.

Historical failures make a quick global switch inappropriate:

- R290's original census merged distinct classes and admitted nondeterministic
  small-shape kernels. Strict-suite passes did not establish broader output
  repeatability. R291 added multi-input fingerprints and deterministic,
  position-invariant and padding-invariant eligibility checks.
- The 27B CLASSPAD experiment used a same-arithmetic oracle; the earlier eager
  reference belonged to a different rounding class.
- A dispatch condition such as `rows > 32` is not a general prefill detector.
  Concurrent decode can also exceed that size, while short prefills and final
  prefill chunks can fall below it. A hybrid adds an arithmetic boundary at
  that threshold.
- Any dynamic selection must remain inside the registered custom op. An
  in-graph Python row-count branch can fail dynamic compilation, and adding
  observation ops can split graphs and alter numerics.

The large historical vocabulary-projection gains were measured with many
concurrent output rows. They do not establish a 512-token prefill opportunity:
the prefill vocabulary projection generally processes selected output rows,
not every input row. Actual per-layer call shapes and time must be profiled.

Given the bounded session and the requirement to preserve exact outputs and
decode speed, no prefill-only CLASSPAD endpoint patch is justified by this
review. This is a scope and evidence decision, not an empirical speed verdict
on an untested candidate.

Supporting source and history:

- [FP16 chunk cost and rounding-class discovery](../../qwen35-4b-b70/notes/2026-09-09-the-fp16-linear-chunk-is-a-throughput-tax.md)
- [R290–R293 server results and census repair](../../qwen35-4b-b70/notes/2026-09-11-r293-class-consistent-fp16-linear-on-the-server.md)
- [27B CLASSPAD results and oracle identity](2026-09-11-r293-class-consistent-fp16-linear-on-the-27b.md)
- [R291 verified census implementation](../docker/r291-fp16-linear-classpad-verified.py)
- [R293 class-selection implementation](../docker/r293-fp16-linear-classpad-cheapest.py)

## One useful profiling step

After baseline measurement, use the existing runtime profiler for one
cache-zero, exactly 512-token request on 4B W4A16 TP2. Keep profiling separate
from the headline timing samples and preserve its configuration and trace.
Inspect the actual FP16 rowchunk call shapes, their contribution to prefill,
and whether repeated small GEMMs or another specific operation dominate.
Do not inject a new model custom op just to collect timings.

Only strong new evidence should open a candidate in this session. If the
trace supports further work, the next bounded task is an operator screen of
the identified shapes, followed by matched full-output and decode checks for
one isolated change. A CLASSPAD hybrid would require explicit new arithmetic
identity and determinism qualification; it cannot inherit the old gates.
Runtime promotion still requires the repository's performance and quality
standards, subject to the user's prohibition on server restart chains.

If profiling shows no inexpensive, well-supported change, finish the measured
baseline publication and retain existing defaults. No optimization win is
claimed by this review.
