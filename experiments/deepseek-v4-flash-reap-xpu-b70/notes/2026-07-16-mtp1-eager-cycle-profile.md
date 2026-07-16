# Exact-Identity MTP1 Eager-Cycle Profile

Date: **2026-07-16**

Status: **profile complete; M=2 router implication promoted**

The exact 60.264242 tok/s record identity was rerun in eager mode under the
Kineto XPU profiler to obtain an operator-shape and kernel-duration map before
another fusion experiment. Raw evidence is external because the four traces
total about 1.44 GB:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-record-eager-cycle-profile-20260716T0550Z`

The reusable streaming summarizer is
`../scripts/summarize-eager-cycle-trace.py`; its tracked output is
`../data/eager-cycle-profile-20260716-summary.json`. It parses the raw files
without loading them into memory.

## Timestamp method and limitation

The XPU GPU-event clock is offset from the host timeline by tens of seconds in
this capture. The summarizer therefore associates kernels with the enclosing
`execute_context_0(0)_generation_1(2)` through each event's host-side
`args.submitted` timestamp, falling back to `appended` or `sycl_enqk_begin`,
while using the GPU event's own `dur` for kernel time. The first decode context
on every rank is discarded.

oneCCL event durations are also distorted in this profile and must not be used
as communication latency. The normal-run 8-9 ms/cycle communication evidence
remains authoritative. oneCCL events are classified separately and excluded
from the 19.478 ms noncollective kernel total.

## Cross-rank mean device buckets

| Bucket | ms/MTP1 cycle |
| --- | ---: |
| Dense `gemm_kernel` projections | 6.5803 |
| Routed MXFP4 MoE GEMM | 4.1511 |
| Native MHC post/pre | 2.8430 |
| Attention QK/LSE | 1.3174 |
| Router radix select | 0.5362 |
| Attention PV | 0.5050 |
| Router radix sort | 0.4829 |
| Other noncollective kernels | 3.0620 |
| **Noncollective total** | **19.4779** |

The bucket durations are eager-profile measurements and not a direct replay
cycle prediction. They are valuable for relative attribution and exact call
shape; end-to-end service controls remain mandatory.

## Corrected router attribution

Every retained rank has nine measured MTP1 contexts and exactly 360
`aten::topk` calls: **40 per cycle**. Every call has input `[2,160]`, `k=6`,
`dim=-1`, `largest=True`, and `sorted=True`. These are the normal target MoE
routers for the two verifier rows, not the Lightning Indexer. The 1K C4
indexer uses its full-selection bypass.

The visible radix select+sort kernels alone cost 1.0191 ms/cycle cross-rank,
before the generic bias, gather, reduction, normalization, scaling, and
intermediate operations. This directly motivated the native M=2 router fusion
promoted in `2026-07-16-mtp1-m2-router-record.md`.

## Next use

The remaining largest unclosed bucket is the 6.5803 ms dense projection path.
The next profile pass should attribute `gemm_kernel` calls by input/output
shape and source projection, then retain only candidates with at least a
0.50 ms measured complete-cycle ceiling. Generic configuration sweeps and
sub-0.50 ms isolated ideas remain closed.
