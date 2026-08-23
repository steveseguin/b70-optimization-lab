# Ornith 1.5 35B-A3B: batched recurrent Q/K L2 is performance-negative

Date: 2026-08-23 EDT

Status: **CLOSED PERFORMANCE NEGATIVE — do not ship**

Ornith's Qwen-derived recurrent stack contains 30 adjacent, independent Q and
K L2 normalizations with shape `[128,16]` in each one-token target graph. An
earlier attempt called the stock helper twice inside each work-group and
changed fixed-seed generation. A pointer-range diagnostic tested the suspected
allocator-lifetime explanation on the actual one-token graph. The Q source, Q
destination, K source, and K destination were all distinct 8,192-byte ranges;
none of their six pairwise range comparisons overlapped. Both normalized
outputs had one graph consumer.

The repaired candidate retained one stock L2 helper invocation per work-group
and used a leading two-element grid dimension only to batch Q and K into one
SYCL submission. Its matcher required the exact names, shape, types,
contiguity, equal epsilon, single-use outputs, and all four pairwise-disjoint
allocations. This removes one submission per recurrent layer without combining
the two subgroup reductions inside a work-group.

## Correctness

The strict 128-token, seed-42 greedy comparison was byte-identical. Both
extracted transcripts had SHA-256
`2e7965fcdc273f0433df359cff5188ae3585426fd32f28536121d1b5e35dad18`.
The candidate recorded exactly 3,810 fused pairs, matching 30 recurrent layers
across the 127 decoded evaluations. This repairs the earlier correctness
failure; it does not make the optimization useful.

## Mirrored decode screen

The same candidate binary was used for all four arms; the default-off runtime
flag was the only condition change.

| Arm | Generation rates (tok/s) | Mean |
| --- | --- | ---: |
| control | `84.6`, `84.4` | **84.50** |
| batched Q/K L2 | `83.5`, `85.2` | **84.35** |

The directly measured delta is **-0.18%**. The candidate runs straddle the
controls and the mean is slightly lower, so it did not earn a fresh-server
test. No throughput is inferred from the 30 removed submissions.

The accepted eleven-feature source and binaries were restored after the test.
The exact diagnostic and candidate source is retained at
`../patches/llamacpp-ornith15-qk-l2-batched-performance-negative-20260823.patch`;
the structured result is
`../data/2026-08-23-ornith35b-qk-l2-batched-summary.json`.
