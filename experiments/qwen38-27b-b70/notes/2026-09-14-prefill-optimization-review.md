# Bounded prefill optimization review

September 14, 2026. This source and evidence review accompanies a focused effort
to fill useful missing 512-token, one-user prefill measurements. It does not
establish a performance improvement or change a serving default.

The user requested a modest follow-up, not an exhaustive optimization campaign.
Two options were reviewed. Neither warranted a new endpoint patch within this
scope. One runtime-profiler trace on the 4B W4A16 two-card setup is now
complete. It identifies many small FP16 matrix multiplications as a substantial
cost, but establishes no new inexpensive arithmetic-preserving candidate.

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

## Completed profiling step

The [trace analysis](../data/2026-09-14-prefill-trace-analysis.json) covers one
cache-zero 512-input-token request with one returned token on 4B W4A16 TP2.
The returned token matched the unprofiled baseline. The runtime's existing
profiler collected both worker traces; no custom model probes were inserted.
Profiling was stopped before the final unprofiled control measurements.

| Device operation group | Rank 0 | Rank 1 | Interpretation |
| --- | ---: | ---: | --- |
| FP16 matrix multiplications | 27.418 ms | 28.843 ms | 907 calls per rank; 848 use 32 input rows |
| INT4 matrix multiplications | 19.876 ms | 19.369 ms | 83 calls per rank |
| Directly attributed GDN kernels | 7.909 ms | 7.860 ms | 168 kernels per rank |
| Allreduce | 9.023 ms | 21.960 ms | Includes possible synchronization waiting; not pure transfer cost |

These are summed traced device-kernel durations within each rank, not unprofiled
request latency or additive savings. Do not add the ranks together. The trace
includes MTP work even with only one returned token. Inclusive CPU operator
intervals nest and are reported separately in the analysis. The full-vocabulary
FP16 projection has one row, confirming that it is not a 512-row projection.

The rowchunk operations and their device descendants account for 29.391 ms on
rank 0 and 30.791 ms on rank 1, about 40.2% and 36.4% of each rank's summed
kernel durations. Fifty-three larger rowchunk calls produce the 848 small
GEMMs. This is a concrete target for future work, but not proof that their
required arithmetic can be preserved by a faster implementation.

Decision: retain the existing defaults. The already-screened allocation change
is not rerun, and the new-arithmetic CLASSPAD hybrid is not patched into the
server. A later bounded optimization task could screen one implementation that
batches these fixed 32-row operations while preserving their exact kernel
arithmetic, then immediately apply matched output and decode gates. Building
and qualifying such a kernel is beyond this measurement follow-up. No new
candidate was benchmarked or promoted in this session.
