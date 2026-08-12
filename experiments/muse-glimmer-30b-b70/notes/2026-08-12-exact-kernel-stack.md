# Exact BF16 kernel stack: consolidated result

Date: 2026-08-12

> **Correction (later 2026-08-12 audit):** `GGML_SYCL_BF16_PAIR=1` does not
> execute in the TP4 target path. The meta backend places gate and up
> projections in distinct per-device subgraphs at tensor-parallel reduction
> boundaries, while the source optimization only recognizes adjacent nodes in
> one subgraph. A runtime graph dump and an explicit execution marker confirmed
> zero pair hits. Therefore the earlier +2.10% pair attribution was noise, and
> the 64.012 t/s combined row is a primitive/binding-cache observation with a
> dead pair flag, not evidence for shared conversion.

## Result

The exact stack combines:

- `GGML_SYCL_DNNL_GEMM_CACHE=1`;
- `GGML_SYCL_DNNL_GEMM_BIND_CACHE=1`;
- `GGML_SYCL_BF16_PAIR=1`.

All direct/reordered experimental GEMM paths and SYCL graphs remain disabled.
The adjacent same-binary result is:

| Arm | Prose | Code | JSON | Arithmetic mean |
| --- | ---: | ---: | ---: | ---: |
| primitive-cache control | 44.215 | 63.833 | 77.366 | 61.805 |
| exact wrapper stack | 45.728 | 66.028 | 80.281 | 64.012 |
| improvement | +3.42% | +3.44% | +3.77% | **+3.57%** |

The three output hashes are identical: `914f754747d0edaa`,
`cf2b2c4fd9e36fe5`, and `4f813a9706abc163`. Accepted-token counts are also
identical at 172 / 197 / 207.

Against the original adjacent comparator from the primitive-cache experiment
(55.533 tok/s), the complete exact kernel candidate reaches 64.012 tok/s, a
measured **15.27%** improvement. The exact comparison to the original arm
spans builds/windows, so 15.27% is the campaign delta; 3.57% is the strict
same-binary stack delta above the primitive cache.

Raw result:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/exact-kernel-stack-ab-20260812.jsonl`;
- SHA-256 `72792f79d8ce95fcdabd57ad3d039f62ebc030bea6bd8856d3afe86a7bda2e47`.

## Ceiling decision

The fixed-suite mean remains 64.012 tok/s, not 100. oneDNN verbose confirms
that BF16 projections already execute through the GPU `jit:gemm:any`
implementation. The synchronized profile and verbose trace identify large FFN
GEMMs as the dominant device work, near the weight-bandwidth floor. Therefore
additional launch/wrapper micro-optimization cannot plausibly supply the
remaining 56.2%.

The campaign must now change one of two larger terms without drafter training:

1. permit a non-byte-identical but target-self-consistent matrix-library
   implementation and put it through a wider quality/equivalence gate; or
2. increase useful target-verified tokens per weight pass through a valid
   serving/verification structure.

Naive two-block DFlash batching is invalid because block two needs target
features from block one. A 16-row top-k tree is target-exact but independently
projects only about 1--5%, so it is not the primary path to 100.
