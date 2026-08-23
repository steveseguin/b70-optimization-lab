# Ornith 1.5 35B-A3B: MTP Q4_K 32-row geometry is neutral

Date: 2026-08-23 EDT

Status: **CLOSED NEUTRAL — exact, fully active, not shipped**

The preferred MTP1 verifier dispatches the Qwen-derived alpha and beta
projections through reordered two-column Q4_K MMVQ. Each matrix has only 32
output rows, so this ladder tested whether the general 16-subgroup workgroup
packing was oversized. The default-off diagnostic changed only subgroup
packing for exact `[2048,32]` weights and two FP32 activation columns; the
dot-product function, quantized input, accumulation, and stores were unchanged.

All three fixed-seed 128-token continuations were byte-identical. Each treatment
reported 4,980 live calls, covering all 60 alpha/beta projections per verifier
cycle.

| Subgroups/workgroup | Generation |
| ---: | ---: |
| 16 (stock) | `65.1 tok/s` |
| 8 | `65.2 tok/s` |
| 4 | `64.9 tok/s` |

The eight-subgroup change is noise-scale and the four-subgroup endpoint is
slower. No fresh-server screen or extrapolated gain is reported. The result
suggests these small projections are governed more by their fixed activation
quantization and dispatch sequence than by workgroup packing.

The incremental diagnostic is preserved at
`../patches/llamacpp-ornith15-mtp-q4k-32row-geometry-neutral-20260823.patch`.
Raw output and the structured decision use the
`../data/2026-08-23-ornith35b-mtp-q4k32-*` prefix. The accepted source and
binaries were restored after the ladder.
