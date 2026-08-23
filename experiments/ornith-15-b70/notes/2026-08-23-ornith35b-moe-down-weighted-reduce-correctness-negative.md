# Ornith 1.5 35B-A3B: routed-down tail reinvestigation

Date: 2026-08-23 EDT

Status: **CLOSED CORRECTNESS NEGATIVE — no performance claim**

The serialized current-stack profile ranked routed down plus its weighting and
ordered reduction as the largest remaining bounded MoE tail. Those diagnostic
times were used only to select the boundary; they were not converted into a
throughput estimate.

Three progressively more conservative implementations were tested behind
`GGML_SYCL_FUSED_ORNITH_MOE_DOWN_REDUCE=1`:

1. one work-group per output row, preserving the reordered Q4_K dot loop and
   rounding each expert dot and route-weight product through local FP32;
2. the same fused dot kernel, but forcing both intermediates through the
   original graph-visible global FP32 tensors;
3. the stock reordered routed-down projection unchanged, followed by one
   kernel that wrote route-weight products through the real weighted tensor and
   performed the already-accepted expert-order reduction.

Each same-binary door-off control produced the accepted canonical SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
All three candidates fired 2,540 times and changed deterministic generation:

| Variant | Candidate library SHA-256 | Canonical output SHA-256 |
| --- | --- | --- |
| local dot/product boundaries | `bca104ad4199050141d0cd0dafd77f511f44a4f9453ced16525564a35b7af0f0` | `df9725e4adb4e34ddcfdf1b822b0b8465d150e35cf5fe8a0d9740e7a81a88023` |
| global dot/product boundaries | `537edf4c4391cd591cb935a32cb3a33c12d18807e62fcda1096cb2e9febebcee` | `9f594c8cb829449a99863d2fa3ab3742b7b40403ae5538f1d47435b53bb04340` |
| stock down plus global weighted reduction | `611ccbd41d75de3132137972b2c6c130e7c40ff21babd0a0d7569856a7081009` | `4e55ff45d4ed00396b0ae54a07669c9a3df5c5df9b09dcc2b4ef8f46ed79ede6` |

The last variant proves that changing the routed-down kernel geometry is not
the only issue: even retaining the production projection and materializing the
real weighted tensor does not reproduce the stock `MUL` plus separate ordered
reduction closely enough. No speed benchmark was run after the failed
correctness gate.

Keep the accepted stack unchanged. The complete rejected source is archived as
`../patches/llamacpp-ornith15-moe-down-weighted-reduce-correctness-negative-20260823.patch`;
structured evidence is beside the profiler data.
