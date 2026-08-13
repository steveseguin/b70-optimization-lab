# Muse oneDNN operand-layout screen

This standalone screen tests an exact-layout alternative for the dominant
BF16 verifier projections.  The incumbent llama.cpp SYCL wrapper presents the
operation to oneDNN as:

```text
W[M,K] x A[K,N] -> C[M,N]
```

with the static model matrix bound as `DNNL_ARG_SRC`.  The candidate uses the
transpose identity:

```text
A^T[N,K] x W^T[K,M] -> C^T[N,M]
```

The raw BF16 inputs and F32 output allocation are unchanged; only the oneDNN
descriptors and argument roles change.  This puts the static model matrix in
`DNNL_ARG_WEIGHTS` and may select a better small-N Xe2 GEMM blocking policy.

The harness also compares true 2D descriptors against llama.cpp's current 3D
batch-of-one descriptors.  Batch removal is another descriptor-only change:
it does not alter pointers, strides, dtypes, or the reduction dimension.

The first gate is the TP4 Muse gate/up shard shape `M=4992, N=16, K=6656`.
Advance to a llama.cpp default-off experiment only if the candidate is
bit-exact to the incumbent and materially faster in an isolated adjacent A/B.
This harness does not modify or stop production.

## Result: closed

All descriptor variants were bit-exact, but none was materially faster.  The
final 500-iteration screen measured:

| Shape | Installed 3D control | 3D transposed | 2D incumbent | 2D transposed |
| --- | ---: | ---: | ---: | ---: |
| gate/up `4992x16x6656` | `0.116225 ms` trailing | `0.115971 ms` | `0.116006 ms` | `0.116346 ms` |
| down `6656x16x4992` | `0.116792 ms` trailing | `0.116774 ms` | `0.116748 ms` | `0.116762 ms` |

The colder leading control was slower, so pooled A/B/A values superficially
favored the candidate.  The warmed trailing control shows the real result:
all variants are within about `0.3%` and the down projection is effectively
identical.  Do not add an operand-swap or 2D special case to llama.cpp.

Official oneDNN `v3.12` (`80afa71049cd69a3df32adcccb623b12cd7baa22`)
was then built with the oneAPI 2026 compiler and tested through the same
harness.  It matched the installed 3.11.2 output hashes exactly:

- gate/up: `0xe0919d3586cdf201`;
- down: `0x515b4548da98251e`.

Its warmed times were likewise neutral (`0.115883--0.116276 ms` gate/up and
`0.116736--0.116844 ms` down across the four descriptor forms).  A oneDNN
3.12 upgrade is not a Muse verifier kernel win on these shapes.

A final v3.12 developer-mode strategy screen explicitly forced the selected
Xe2 `16x16` kernel and three nearby catalog recipes.  Only the selected
strategy reproduced the canonical F32 hash (`0xe0919d3586cdf201`), at a warmed
`0.115596 ms`.  The alternatives produced hashes
`0xbae1b343ab4f7ed2` or `0xe45bb718d2a8a6a6`; the same-layout alternative was
also about 17% slower.  Manual `GEMM_KERNEL` overrides are therefore closed.

External logs:

- `synthetic-first-20260813.log`, SHA256
  `9160f384c86c40a8ba980961446590350c33edff0c80e2ca512e7c32e2baaa83`;
- `synthetic-2d-20260813.log`, SHA256
  `e23567f98fa9c242501c0ee5b40f03e403e8647c75a88bd93a77c0e46cd8efd8`;
- `v311-v312-20260813.log`, SHA256
  `8992642dcc50d28b843da64f3d1b8313ed2b9939cc21a444377c09341df41324`;
- `v312-strategy-20260813.log`, SHA256
  `6cb9fe6aa6e8f47939db4c5a80b2036f5380070651d3a9128c94ac1230ad2ef4`;
- `v312-dev-strategy-sweep-20260813.log`, SHA256
  `a3da61607fa736f5df2dc9d77189c571e49b6e4d564274052905c83d8c02c501`.

They are under
`/mnt/fast-ai/bench-results/muse-glimmer-30b/onednn-operand-layout/`.
Every GPU window used the canonical exclusive lock and cleanup trap.
Production passed the full cache-zero code and vision health gate after the
final window in
`data/muse-health-20260813-onednn-dev-strategy-restore.json`.
