# Nonspeculative M=1 bandwidth-roofline profile

Date: 2026-07-19

## Result first

The exact-source, graph-on nonspeculative lane passed the sanity gate at
`43.703604 tok/s` median, or `22.881408 ms/token`, across 12 fixed rapid
realistic prompts. All 12 responses had `cached_tokens=0`. This is the expected
43-44 tok/s lane, not the approximately 15 tok/s graph-none failure mode.

The bounded additive decomposition is:

| Bucket | ms/token | Cycle | Removable? |
|---|---:|---:|---|
| Weight-streaming GEMMs: dense projections, routed experts, shared expert and LM head | 10.089 | 44.09% | floor/partial: `7.270` floor plus `2.819` kernel-efficiency slack |
| Host submission, scheduler and outer queue gap | 3.435 | 15.01% | yes |
| Norms, MHC, RoPE, KV insert and miscellaneous elementwise work | 3.310 | 14.47% | partial |
| TP4 all-reduce critical-path contribution | 2.746 | 12.00% | yes/partial; serialized upper bound is `5.601` |
| MoE route/select/normalize, activation and direct gather/scatter | 1.842 | 8.05% | yes/partial |
| Sparse attention QK/LSE and PV, excluding projections | 1.460 | 6.38% | partial |
| **Total** | **22.881** | **100.00%** | |

The established streaming floor is `7.270 ms/token`; therefore removable
overhead is `22.881 - 7.270 = 15.611 ms/token`. The measured weight-kernel
time is `10.089 ms/token`, 38.8% above the floor, corresponding to about
`1520 GB/s` effective aggregate weight bandwidth, or 72.0% of the
`2110 GB/s` roofline. The table reconciles by construction to the measured
cycle with less than `0.002 ms/token` rounding residual. Section
"Measurement and bounds" explains the two residual/overlap allocations rather
than presenting them as independent direct event sums.

## Exact identity

This run used detached worktrees at the requested commits, not the current
development heads:

- vLLM `a681dbb2b4b19c2c5a964817095b5f8c1f27ff48`;
- XPU kernels `6522849b02894273b1e779b3c115527b5cdf3756`;
- oneCCL source `48fda4f0e074db005596d6899d5227d3f0316c12`;
- loaded oneCCL
  `/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib/libccl.so.1.0`,
  SHA-256
  `53de2b6d65265803d64773546c1166ceed4ae43737f0fded776f5847b4b461c9`;
- model revision `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- TP4+EP4, FP8 KV cache, block size 256, prefix cache disabled;
- `XPU_GRAPH=1`, `VLLM_XPU_ENABLE_XPU_GRAPH=1`, `ENFORCE_EAGER=0`, and
  `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE"}`;
- `VLLM_XPU_V4_M1_ROUTER_NORM=1` and
  `VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE=1`;
- speculation was absent from the command and
  `VLLM_XPU_DSPARK_SPEC_TOKENS=0`; all DSpark, Markov, history and rejected
  speculative flags were explicitly zero;
- graph-with-communication force/no-op-capture flags were zero.

The XPU extension was rebuilt cleanly from that exact source revision. It is
therefore an exact-source replay rather than a byte-for-byte replay of the old
incremental extension binary. The freshly built native hashes were:

- `_xpu_C.abi3.so`:
  `e000c204a9f75bced9ee61370e80543f3a3dd3aecb848c9df2d9afc015eee55d`;
- `libgrouped_gemm_xe_2.so`:
  `8adcdde27e91ba8d5015e045ca5e3fba2c5332841bbf384a9dafc19cd9984eac`;
- `_C.abi3.so`:
  `536a0c3db31b4ad4639dac160d98ef11575bc0feb10631264f1b80da23693731`;
- `_moe_C.abi3.so`:
  `3781a518bb41566c6ef67cbffca9fba23e22a413868ca0d39b6037700e33bc28`.

The strict sanity result is
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-m1-roofline-profile-20260719T140812Z/sanity-strict.json`:

- median `43.703604435687666 tok/s`;
- p10 `43.19850167119631 tok/s`;
- mean `43.64893141197897 tok/s`;
- 12/12 cache-zero rows, gate passed.

## Measurement and bounds

The service was loaded once. The production throughput measurement is the
cycle authority; profiling measurements only apportion that cycle.

1. A PIECEWISE XPU-graph trace retained eight M=1 decode contexts per rank.
   After discarding profiler startup/serialization outliers, the median of the
   final five `execute_context` durations was `19.447 ms` on the slowest rank.
   The production cycle minus that duration is the directly observed outer
   host/scheduler/queue gap: `22.881 - 19.447 = 3.435 ms/token`.
2. The graph body is intentionally opaque to Kineto. A phase-correct real-shape
   eager device-event trace from the same tuned weight/attention path supplied
   the stable kernel buckets: dense GEMMs `6.604`, routed-expert GEMMs `3.485`,
   sparse QK/LSE `1.159`, PV `0.301`, and MHC post/pre `2.913 ms/token`.
   Dense plus routed-expert GEMMs is `10.089 ms/token`; dense includes the
   attention projections, shared expert and head. This trace predates the
   native router/direct-gather boundary, so its old router/gather measurements
   were not carried forward.
3. Current exact four-card component gates replace those old MoE boundaries.
   Direct routed-MoE averaged `106.547 us/layer * 43 = 4.582 ms/token`.
   Subtracting its routed GEMMs gives `1.096 ms/token` of activation and direct
   gather/scatter. Native route/select/normalize averaged
   `18.639 us/layer * 40 = 0.746 ms/token`. Their total is the current
   `1.842 ms/token` non-GEMM MoE bucket.
4. A post-service same-device XPU-event harness measured 87 ordered TP4
   BF16[4096] all-reduces, matching the M=1 collective count and shape. The
   slowest-rank median was `5.601 ms/token` device time and `5.978 ms/token`
   wall time over 24 exact epochs. This is a serialization/no-overlap upper
   bound, not an additive serving cost. The live critical-path allocation is
   `2.746 ms/token`: the remaining graph-body time after weight GEMMs,
   attention, current non-GEMM MoE, and the norms/MHC/misc bucket. Thus at
   least about `2.855 ms` of the standalone collective chain is hidden by
   overlap or absorbed into the graph transaction.
5. The `3.310 ms/token` norms/MHC/RoPE/KV/misc bucket is anchored by the direct
   `2.913 ms/token` MHC measurement; its remaining `0.397 ms/token` is the
   bounded residual for fused norm/RoPE/KV insertion and small elementwise
   kernels. Queue bubbles inside the opaque graph cannot be separated further
   without disabling the very graph mode that makes this lane valid.

The PTI trace itself strongly distorted oneCCL: one profiled request fell to
about `0.44 tok/s`, and ranks showed startup/serialization outliers up to about
35 seconds. Consequently, Kineto oneCCL event durations are rejected. The
standalone XPU-event number is an upper bound and the reconciled live
critical-path number is the figure used in the additive table.

Artifacts:

- run identity, server logs, strict gate and request:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-m1-roofline-profile-20260719T140812Z`;
- graph traces and summary: the `trace/` directory and
  `graph-trace-summary.json` below that run;
- exact-shape collective result: `tp4-87-wideepoch.json` below that run;
- phase-correct device-event source trace:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/record-lane-eager-tuned-profile-20260715T0730Z`;
- current router component:
  `data/m1-router-normalization-four-card-20260715.json`;
- current direct-MoE component:
  `notes/2026-07-15-m1-direct-routed-moe-four-card-gate.md` and its linked
  four-card gate outputs.

## Ordered nonspeculative roadmap

Ranked by additive removable contribution, with the roofline slack separated
from the irreducible weight stream:

1. **Host/scheduler/outer queue gap -- 3.435 ms/token.** Move output handling,
   metadata preparation and the next decoder transaction onto a fixed-address
   device-resident path; remove the inter-step engine/Python submission gap.
2. **Norms/MHC/RoPE/KV/misc -- 3.310 ms/token.** Fuse the repeated MHC
   post/pre, norm/residual and KV-insert boundaries into their consumers, or
   carry them through a persistent layer/decoder transaction. MHC alone is
   `2.913 ms/token`.
3. **Weight-kernel efficiency slack -- 2.819 ms/token.** Co-design the
   fixed-shape dense/MXFP4 kernel portfolio and command stream to approach the
   measured bandwidth roofline; target dispatch/tile inefficiency and
   next-weight staging without changing weight precision.
4. **TP4 collective critical path -- 2.746 ms/token additive,
   `5.601 ms/token` serialized upper bound.** Own producer, low-latency ring,
   and MHC consumer in one device transaction so more of the chain overlaps or
   disappears from the critical path.

Eliminating the top two additive buckets gives
`22.881 - 3.435 - 3.310 = 16.137 ms/token`, or **61.97 tok/s**. That is the best
plausible immediate nonspeculative estimate before recovering weight-kernel
slack or additional communication overlap; it is not a record claim.

No LocalMaxxing submission was made and no source/throughput record is claimed
from this diagnostic run.
