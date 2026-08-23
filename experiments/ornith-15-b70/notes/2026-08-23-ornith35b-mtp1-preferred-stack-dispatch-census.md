# Ornith 1.5 35B preferred-MTP1-stack dispatch census

## Outcome

With the exact two-row residual/RMS and ordered-MoE research fusions enabled,
the steady target verifier dispatches **1,042** generic SYCL kernels, down from
the directly measured pre-stack 1,442. The embedded draft remains 29 launches.

This is a diagnostic count at the final generic dispatch point. It does not
imply or extrapolate throughput.

## Measured change

| graph | before preferred stack | after preferred stack | change |
| --- | ---: | ---: | ---: |
| two-row target verifier | 1,442 | 1,042 | -400 |
| embedded MTP draft | 29 | 29 | 0 |

The target verifier's surviving operation classes are:

| op | launches/cycle |
| --- | ---: |
| MUL_MAT | 311 |
| UNARY | 130 |
| MUL_MAT_ID | 120 |
| MUL | 110 |
| GET_ROWS | 61 |
| CPY | 60 |
| L2_NORM | 60 |
| GLU | 40 |
| ADD | 30 |
| CONCAT | 30 |
| SSM_CONV | 30 |
| ROPE | 20 |
| SET_ROWS | 20 |
| FLASH_ATTN_EXT | 10 |
| CONT | 10 |

The preferred stack removes 400 ADD dispatches: the ordered routed-expert
chains and the residual/RMS boundaries. The remaining 30 ADDs are the
recurrent alpha-bias operations. Counts are identical across four captured
steady target graphs.

## Interpretation

The remaining elementwise classes decompose cleanly:

- 30 convolution SiLU, 30 alpha softplus, 30 beta sigmoid, and 40 shared-gate
  sigmoid launches account for all 130 UNARY;
- 30 alpha-gate, 40 weighted-expert, and 40 shared-expert-gate products account
  for all 110 MUL;
- recurrent rollback handling accounts for 30 CONCAT, 60 CPY, and 30 of the 61
  GET_ROWS.

The alpha, convolution, and two-snapshot state transfers have now been measured
separately and retained only where supported. This census points to beta/GDN
integration as the least-repeated recurrent elementwise boundary; shared-gate
broadcast is lower priority because its exact target-only server screen already
regressed.

Raw trace:
`../data/2026-08-23-ornith35b-mtp1-preferred-stack-dispatch-census.log.gz`.
The existing diagnostic patch is
`../patches/llamacpp-ornith15-mtp-actual-census-diagnostic-20260823.patch`.

