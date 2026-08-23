# Ornith 1.5 35B-A3B: decode launch census and two correctness negatives

Date: 2026-08-22 EDT

Status: **profiling result; two candidates rejected before performance screening**

## Effective-fusion census

An opt-in diagnostic build dumped the one-token SYCL graph and reported every
backend fusion that actually fired. The graph has 3,726 nodes including views
and 2,234 compute nodes. The repeated compute operations include 430 `ADD`, 391
`MUL_MAT`, 281 `MUL`, 170 `UNARY`, 131 `RMS_NORM`, 120 `MUL_MAT_ID`, 60
`L2_NORM`, and 30 `SSM_CONV` nodes.

Several apparent opportunities are already banked by the backend. Per decode
graph it matched all 40 top-k MoE router chains, 30 GDN-cache tails, 40
matmul/GLU groups, 131 RMS-norm/multiply pairs, and 70 unary/multiply pairs.
The lab stack additionally matched all 40 ordered MoE reductions and all 30
Ornith convolution/SiLU pairs. Raw graph-node counts are not kernel timings and
are not used to extrapolate throughput.

The structured census is in
`../data/2026-08-22-ornith35b-launch-census-negatives.json`; the compressed raw
diagnostic trace is beside it.

## Rejected: paired Q/K L2 normalization

The 30 recurrent layers each have independent `[128,16]` FP32 Q and K L2
normalizations. Pairing them would remove one launch/layer. Both a combined
32-row kernel and a stricter 16-row kernel that called the exact stock helper
twice matched all 30 layers but changed fixed-seed greedy generation. The
strict 128-token comparison hashes were:

- door off: `e38c46d2d9c68451a3745612fbea15496a9726e64b277ef6b3bb0457b2a50c2d`;
- door on: `5d80f55e9d797937eb8494c9ea05dde498f566e3c84fb7569f91bcc63880bdee`.

No speed result was promoted. The exact rejected source is archived as
`../patches/llamacpp-ornith15-qk-l2-pair-correctness-negative-20260822.patch`.

## Rejected: shared-expert gate tail

Each MoE layer ends with scalar gate sigmoid, broadcast multiply of the shared
expert output, and add to the routed expert result. Three increasingly strict
forms were tried: all three operations fused; stored sigmoid with a volatile
private product; and stored sigmoid with the product written to and read from
the graph's actual volatile global intermediate. All matched 40/40 layers and
all changed fixed-seed greedy generation. The strict final 128-token hashes
were:

- door off: `49915ec3740fab76f406e78ff7a7aa31fb3c8de3612355d95cb53483638d5a75`;
- door on: `7d2e4190e8d5e4b38c368efb33aa834085e7a5a2d060de9c48aaa466652acb32`.

No speed result was promoted. The strict final source is archived as
`../patches/llamacpp-ornith15-shared-mul-add-correctness-negative-20260822.patch`.

## Decision

Keep the published ordered-MoE plus convolution/SiLU stack unchanged. Do not
relax exactness to claim either launch reduction. The next decode candidate
must target a different boundary or first provide tensor-level proof explaining
these generation differences.
