# Full187 + GDN-cache M=6 operation trace

Date: 2026-07-13

## Purpose

Replace the inferred decoder-overhead bucket with a measured operation census
for the current single-B70, full187 Xe2-DPAS, joint-gate/up,
`GGML_SYCL_FUSE_GDN_CACHE=1` DFlash lane.

The diagnostic server log is:

`/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/full187-gdn-optrace-20260713/server-v2.log`

The fixed request emitted 12 tokens, accepted 7 of 15 draft tokens, and reported
a mean speculative length of 3.33. The request response is preserved at
`/tmp/qwen-full187-optrace-response-v2.json` for this host session.

## Important measurement caveat

`GGML_SYCL_OP_TIMING=1` waits on individual events and therefore serializes the
graph. Its per-op `device_us` values are useful as a work census and for ranking
boundaries, but their sum is **not** the production cycle wall time. The joint
gate/up fast path returns before the generic operation timer and is also absent
from this census.

## Warm target-verifier M=6 census

The second and third warm target graphs each contained 2,132 timed operations.

| Bucket | Graph 9 | Graph 13 |
|---|---:|---:|
| Visible timed work | 52,710 us | 52,338 us |
| `MUL_MAT` | 34,131 us | 33,920 us |
| `MUL` | 2,779 us | 2,735 us |
| `CPY` | 2,430 us | 2,419 us |
| `UNARY` | 2,017 us | 2,025 us |
| `RMS_NORM` | 2,017 us | 1,999 us |
| `GET_ROWS` | 1,731 us | 1,736 us |
| `ADD` | 1,619 us | 1,614 us |

The warmed graph-13 matrix-multiply breakdown was:

| Projection family | Timed work | Calls |
|---|---:|---:|
| FFN down | 7,419 us | 64 |
| GDN output | 7,297 us | 48 |
| GDN unnamed 10240-wide projection | 3,880 us | 48 |
| GDN 48-wide projections | 3,808 us | 96 |
| GDN z projection | 3,663 us | 48 |
| Full-vocabulary LM head | 3,303 us | 1 |
| Attention 12288-wide projection | 1,479 us | 16 |
| Other 5120-wide projection | 975 us | 16 |
| Other 1024-wide projections | 732 us | 32 |

## Warm DFlash-draft M=6 census

The second and third five-layer draft graphs each contained 118 timed
operations. They measured 9,643 us and 8,957 us respectively, of which 8,315 us
and 8,134 us were matrix multiplies.

The LM head alone measured 3,515-3,545 us per draft graph. The remaining large
families were the five FFN down projections (1,290-1,328 us), five FFN gate
projections (1,189-1,198 us), and five FFN up projections (1,167-1,174 us).

## Decision

The trace changes the priority order:

1. Integrate and validate the guarded Q6_K M=6 logits-to-top-1 kernel. Both the
   target verifier and the DFlash draft pay roughly 3.3-3.5 ms of serialized
   diagnostic device time to materialize full-vocabulary logits. Eliminating
   that intermediate attacks a repeated, dominant boundary.
2. Use a production, non-serializing cycle A/B to measure the actual wall-time
   reduction. Do not infer the speedup directly from the operation-timer sums.
3. After Q6 top-1, prioritize the recurrent target projections and FFN down
   path. The already prototyped exact SwiGLU-to-Q8 tail remains low priority
   because its realistic isolated gain was only about 0.16-0.44 ms per cycle.
4. Continue to reject generic launch/configuration sweeps. The remaining work
   is a fused persistent decoder and a cheaper speculative cycle.

