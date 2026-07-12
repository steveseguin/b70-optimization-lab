# 2026-07-12 Xe2 verifier v2 comparator audit

## Finding

Do not integrate `joint-2` from the standalone verifier on the strength of the
reported 4.8x--13.1x result.  The comparator named `repeated_vector` launches
one output work-item for every `(M,N)` element and therefore rereads the packed
weight stream once for every verifier row.  The active llama.cpp kernel does
not have that behavior.

`reorder_mul_mat_vec_q4_0_q8_1_sycl_ncols<4/8>` assigns one output-weight row
to a subgroup, loads each Q4 block once, and accumulates all 4 or 8 activation
columns in an unrolled inner loop.  Consequently the standalone result compares
joint-2 with an intentionally weaker vector mapping rather than the production
MMVQ verifier.  Its correctness evidence remains useful, but its promotion
speedup is invalid.

## Runtime disposition

The attempted guarded runtime integration was removed before dispatch was
changed.  `GGML_SYCL_XE2_VERIFIER_V2` is not implemented and M=1/M=4/M=8 keep
using the existing runtime paths.

An experiment-only launcher,
`ggml_sycl_bench_reorder_q4_0_ncols`, now exposes the exact active width-4/8
kernel from `mmvq.cpp`.  The JIT `ggml-sycl` target compiled and linked with the
hook.  The next benchmark must construct both native reordered-Q4/Q8 SoA and
joint-2 packed inputs from identical quantized tensors, then measure:

1. active Q8 production plus exact active MMVQ;
2. joint-layout Q8 production plus joint-2 compute plus split reduction;
3. KxN = 5120x5120, 5120x17408, and 17408x5120 at M=4 and M=8;
4. output equality after the actual FP16 Q4/Q8 scale conversions.

Integration remains gated on `>=1.5x` against that production total, not the
old repeated-vector surrogate.

## Production-comparator result

The exact-production comparison closes this integration lane.  Total timings
include runtime Q8 production and all candidate submissions (joint-2 compute
plus its split reduction):

- M=4, 5120x5120: `1.407x`, FAIL;
- M=4, 5120x17408: `1.374x`, FAIL;
- M=4, 17408x5120: `1.662x`, but the output difference was approximately
  `0.8`, so correctness failed;
- M=8, 5120x5120: `1.925x`, performance pass.

MTP3's critical M=4 verifier misses the required `1.5x` total-speed gate on
two of the three real projection shapes.  One apparent M=4 speed pass also
misses correctness, and an M=8-only win cannot justify a production verifier
whose normal cycle verifies four rows.  Therefore no runtime dispatch or
`GGML_SYCL_XE2_VERIFIER_V2` flag should be added from this design.

Disposition: preserve the harness and exact-production benchmark hook as
negative-result evidence, but reject joint-2 split/reduce runtime integration.
