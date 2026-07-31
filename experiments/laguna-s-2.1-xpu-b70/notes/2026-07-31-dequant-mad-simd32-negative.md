# Laguna INT4 full-pair SIMD32 dequant-MAD: static neutral

Date: 2026-07-31 America/Toronto

Status: **closed at the first ISA gate**. The SIMD32 vISA form compiled, but
the final BMG ISA is instruction-for-instruction neutral in aggregate. No full
production DSO build, component test, model load, generation, scored leg,
throughput claim, or recovery action occurred.

## Identity and result

- source base: `46a88e09d96fe06871c87a23de534fb47f1e039b`;
- negative candidate: `7557817d0e8c564be74f2cd7717e0195c1cb3911`;
- branch: `experiment/laguna-mad-simd32-20260731`;
- probe policy: `w4a16_policy_m_8`, group size 32, 256-GRF BMG backend;
- incumbent IGC root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-mad-inplace-incumbent2-20260731T0821Z`;
- corrected candidate IGC root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-mad-simd32-candidate2-20260731T0833Z`.

The candidate presented each adjacent pair of FP32 scales and biases as one
two-element per-work-item operand and replaced the two source-level
`mad (M1, 16)` statements with one `mad (M1, 32)`. This is elementwise and
preserves every numeric operand and BF16 rounding point.

| Native BMG count | Incumbent | SIMD32 candidate |
| --- | ---: | ---: |
| total instructions | **376** | **376** |
| DPAS | 2 | 2 |
| BF16 MAD | 32 | 32 |
| total `mad` including address arithmetic | 33 | 33 |
| total `mov` | 156 | 156 |
| total `add` | 37 | 37 |
| total `mul` | 6 | 6 |

IGC accepts the SIMD32 vISA, then the BMG finalizer lowers it into the same two
native SIMD16 halves. The first half uses execution mask `M0`; the second uses
`M16`. The earlier probe summary counted only `M0` and briefly printed 16
BF16 MADs. The durable runner now counts every numeric mask, and the corrected
root reports 32. The full mnemonic census independently confirms the identical
33/156/376 totals.

The candidate therefore fails the preregistered requirement to reduce total
instructions by at least eight. A full 42-minute extension build and all GPU
stages were skipped.

## Reusable finding

Widening vISA execution width is not evidence of fewer native Xe2 issue slots.
For BMG BF16 MAD, SIMD32 is finalized as two SIMD16 operations. Always inspect
final IGC assembly and include nonzero execution masks (`M16`, not only `M0`)
when counting widened instructions.

Artifacts:

- preregistration:
  `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-dequant-mad-simd32-preregistration.md`;
- structured result:
  `data/laguna-dequant-mad-simd32-negative-20260731.json`;
- review patch SHA-256:
  `fdf90dbd88fcdf6f507df2fd5123fc15f0de46c35daa43d69918911a19b68549`;
- source bundle SHA-256:
  `38933d1eb3561fcddf6c00cea5d6c7d629bddc518b6593a0e67e17856047f496`.

