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

## Exact dense-GEMM decomposition

Schema v2 of the tracked summary attributes every `gemm_kernel` event to its
enclosing operator and exact shape. The largest cross-rank mean families are:

| Projection family | Exact M=2 shape | ms/cycle | Status |
| --- | --- | ---: | --- |
| `wo_a` BF16 BMM | `[2,2,4096] x [2,4096,1024]` | 1.4094 | FP8 replacement already closed end to end |
| WQ_B W8A16 | `1024 -> 8192` | 0.9129 | already optimized |
| WO_B W8A16 | `2048 -> 4096` | 0.8183 | already optimized |
| C4 compressor BMM | `4096 -> 2048`, 21 calls | 0.6960 | row-exact batched path promoted |
| fused WQA/WKV W8A16 | `4096 -> 1536` | 0.6305 | already optimized |
| shared-down W8A8 | `512 -> 4096` | 0.5919 | activation/quant producer already fused |
| shared gate/up W8A16 | `4096 -> 1024` | 0.4940 | already optimized |
| LM head | `4096 -> 32320` | 0.4473 | single cycle boundary |
| C128 compressor BMM | `4096 -> 1024`, 20 calls | 0.3505 | row-exact batched path promoted |
| router projection | `4096 -> 160`, 43 calls | 0.2150 | consumer selection/normalization now fused |

The 6.5803 ms total is therefore not one untouched dense boundary. Its largest
pieces are already selected, fused, or closed by a measured negative result.

## Next use

The largest genuinely open verifier family is the 4.1511 ms routed MXFP4 path.
The exact N32/N128 small-N policy gate is documented in
`2026-07-16-mtp1-m2-mxfp4-policy-closure.md`: N32 regresses, while N128 saves
only 0.2648 ms/cycle in isolation and does not establish an end-to-end record.
The next candidate must be an architectural M=2 grouped-MXFP4 change with a
measured four-card ceiling of at least 0.50 ms/cycle. Generic configuration
sweeps and sub-0.50 ms isolated ideas remain closed.
