# Ornith 1.5 35B-A3B: reordered-ESIMD work-group endpoints change output

Date: 2026-08-23 EDT

Status: **CLOSED CORRECTNESS NEGATIVE — keep WG4**

The remaining decode graph is dominated by reordered K-quant ESIMD matvecs.
The incumbent kernel assigns four ESIMD work-items to each output-row pair.
For Ornith's common 2,048-wide projections, each worker accumulates two
256-value quant blocks before the four partial sums are added in worker order.

Two narrow compile-time endpoints were screened:

- WG8 assigns one quant block to each worker, then adds eight partial sums.
- WG2 assigns four quant blocks to each worker, then adds two partial sums.

Both retain the same per-block dequantization and MAC implementation, but the
changed partitioning changes FP32 reduction grouping. Both failed the required
fixed-seed 128-token transcript gate:

| Geometry | Extracted transcript SHA-256 | Coarse observed generation |
| --- | --- | ---: |
| accepted WG4 | `2e7965fcdc273f0433df359cff5188ae3585426fd32f28536121d1b5e35dad18` | not re-measured in this compile sweep |
| WG8 | `97dcf80af46eadbb5b0bef866913f27c320afb0970028c1719bc4066650acf20` | 82.5 tok/s |
| WG2 | `57019c28e5c9b2d3e4f2e2af56e6ca4576912411ac780d372dbfd382aaff0407` | 84.5 tok/s |

The observed candidate rates are diagnostic only, not a matched performance
comparison. Once output identity failed, neither endpoint qualified for a
mirrored engine or server benchmark. WG4 remains the validated geometry.

Incremental one-line patches are preserved at
`../patches/llamacpp-ornith15-esimd-wg2-correctness-negative-20260823.patch`
and
`../patches/llamacpp-ornith15-esimd-wg8-correctness-negative-20260823.patch`.
Raw outputs and extracted transcripts are under `../data/ornith-esimd-wg*`;
the structured result is
`../data/2026-08-23-ornith35b-esimd-workgroup-summary.json`.
