# Muse oneDNN operand-layout and v3.12 screen

Date: 2026-08-13

## Decision

Close the oneDNN operand-role, batch-of-one descriptor, and v3.12-upgrade
lanes.  They are exact, but they do not improve the fixed-width BF16 verifier
GEMMs enough to justify a llama.cpp or production change.

## Why this was tested

The retained target-only oneDNN profile assigns about `24.15 ms` per slow-rank
verifier pass to the three FFN BF16 GEMMs.  llama.cpp currently describes each
operation as a 3D batch-of-one `W[M,K] x A[K,N]`, with the static model matrix
bound as `DNNL_ARG_SRC`.  Two descriptor-only alternatives could have selected
a better Xe2 JIT blocking policy without changing bytes or accumulation K
order:

1. transpose the identity to `A^T[N,K] x W^T[K,M]`, placing the static matrix
   in `DNNL_ARG_WEIGHTS`;
2. remove the batch-of-one dimension and use true 2D descriptors.

The installed library reports oneDNN 3.11.2.  Official v3.12 was also built
from immutable tag `80afa71049cd69a3df32adcccb623b12cd7baa22` because its
Intel GPU GEMM generator/selector differs substantially from the installed
source lineage.

## Measurement

The standalone harness uses deterministic BF16 weights and activations, the
exact TP4 MLP shapes, a shared in-order Level Zero queue, user scratchpads, 12
interleaved warmups, and 500 timed executions per arm.  Each candidate output
is compared bitwise to the incumbent and the incumbent output receives a
deterministic FNV-1a hash for cross-library comparison.

Final installed-library results:

| Shape | leading 3D | transposed 3D | incumbent 2D | transposed 2D | trailing 3D |
| --- | ---: | ---: | ---: | ---: | ---: |
| `4992x16x6656` | 0.117693 | 0.115971 | 0.116006 | 0.116346 | 0.116225 |
| `6656x16x4992` | 0.118107 | 0.116774 | 0.116748 | 0.116762 | 0.116792 |

All values are milliseconds per GEMM.  Every mismatch count was zero.  The
leading control is consistently cold-biased; comparisons to the warmed
trailing control leave no material delta.

Official v3.12 reproduced the same F32 hashes and essentially the same times.
It therefore supplies neither a numerical nor a performance reason to change
the production library.

The final bounded screen built the same v3.12 source with
`DNNL_DEV_MODE=ON` and tested explicit `GEMM_KERNEL` strategies from the Xe2
catalog.  oneDNN's default strategy was:

```text
gemm BBS T@16N@16N 16 16 ... wg 2x2x8 ... k64 grf256 ...
```

The explicit default reproduced the canonical gate/up F32 hash
`0xe0919d3586cdf201` and a warmed `0.115596 ms`.  Three nearby legal catalog
strategies all changed the F32 hash, so none satisfies the lossless gate:

| Override | Warmed 3D time | F32 hash | Decision |
| --- | ---: | --- | --- |
| default `16x16`, `wg 2x2x8` | `0.115596 ms` | `0xe0919d3586cdf201` | exact control |
| same-layout alternate `16x16`, `wg 8x4` | `0.135510 ms` | `0xbae1b343ab4f7ed2` | non-exact and slower |
| catalog `16x16`, `wg 4x2x4` | `0.117377 ms` | `0xe45bb718d2a8a6a6` | non-exact |
| catalog `16x4`, `wg 8x4` | `0.148703 ms` | `0xbae1b343ab4f7ed2` | non-exact and slower |

The harness's within-process mismatch checks still pass because an override
applies to all descriptor arms in that process.  Cross-process comparison to
the canonical control hash is therefore the authoritative exactness gate.
Do not manually override the production oneDNN GEMM strategy.

## Artifacts and operational status

Harness:
`experiments/muse-glimmer-30b-b70/onednn-operand-layout/`.

External logs and SHA256 values:

- `synthetic-first-20260813.log`:
  `9160f384c86c40a8ba980961446590350c33edff0c80e2ca512e7c32e2baaa83`;
- `synthetic-2d-20260813.log`:
  `e23567f98fa9c242501c0ee5b40f03e403e8647c75a88bd93a77c0e46cd8efd8`;
- `v311-v312-20260813.log`:
  `8992642dcc50d28b843da64f3d1b8313ed2b9939cc21a444377c09341df41324`;
- `v312-strategy-20260813.log`:
  `6cb9fe6aa6e8f47939db4c5a80b2036f5380070651d3a9128c94ac1230ad2ef4`;
- `v312-dev-strategy-sweep-20260813.log`:
  `a3da61607fa736f5df2dc9d77189c571e49b6e4d564274052905c83d8c02c501`.

No llama.cpp source, model, drafter, or production configuration changed.
Production was restored after each short GPU window.  Final full health:
`data/muse-health-20260813-onednn-dev-strategy-restore.json` (`ok=true`,
`cached_tokens=0`, 512-token code canary, vision=`red`).
