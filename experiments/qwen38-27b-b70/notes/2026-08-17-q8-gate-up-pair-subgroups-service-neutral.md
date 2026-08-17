# Qwen3.8 Q8 fused gate/up workgroup sweep

Date: 2026-08-17

Status: closed endpoint-neutral; do not repeat unchanged

The dominant fused Q8 gate/up pair has exact local shape
`K=5120, N=8704+8704`. This candidate left the SIMD16 DP4A2 row body and FP32
order unchanged, but swept the workgroup population from the accepted
hardware-derived SG8 to 12, 16, 24, and 32 subgroups. The default-off door was
`GGML_SYCL_MMVQ_Q8_PAIR_SUBGROUPS` and only this exact pair shape was admitted.

All modes built for BMG-G31, were live on both ranks, and reported zero
verification mismatches. The mirrored `p64/n256/r3` screen selected SG16. A
fully position-balanced `p64/n512/r3` confirmation then repeated the direct
gain in both blocks:

| Arm | Mean decode |
| --- | ---: |
| accepted SG8 | `37.223653 tok/s` |
| candidate SG16 | `37.712306 tok/s` |
| delta | **`+1.312749%`** |

That attractive microbenchmark result did not survive the required endpoint
gate. Two 12-prompt cache-zero suites were run on each arm using the same
candidate binary, changing only the runtime door. The second pass on each
loaded server gives the fair warmed comparison:

| Metric | SG8 control | SG16 treatment | Delta |
| --- | ---: | ---: | ---: |
| conventional 99-interval median | `37.452276` | `37.426361` | `-0.0692%` |
| full decode median | `37.550550` | `37.507128` | `-0.1156%` |
| full wall median | `37.082444` | `37.053957` | `-0.0768%` |

All 48 endpoint outputs were hash-exact and all cached-token counts were zero.
The pooled conventional result was also negative (`-0.1445%`). This is not a
deployable gain: retain SG8 for the pair and do not promote the door. Both B70s
remained normal; accepted source and library were restored byte-for-byte.

- candidate source SHA-256:
  `342d400bda5934af086eb325e412ff38881257ba4faa0d507ea7a660a5ded993`;
- candidate library SHA-256:
  `b108d3e178644f7b89f44737547aec39804dc77a0387d277365fcbf553dd2379`;
- accepted source SHA-256:
  `a4570708075939e3f28bd127a52d4c38f717ecc5d19ba15cfb7ca0d4dffbedf7`;
- accepted library SHA-256:
  `e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`;
- exact candidate increment:
  [`../patches/q8-gate-up-pair-subgroups-service-neutral-20260817.diff`](../patches/q8-gate-up-pair-subgroups-service-neutral-20260817.diff);
- structured measurements:
  [`../data/2026-08-17-q8-gate-up-pair-subgroups-service-neutral.json`](../data/2026-08-17-q8-gate-up-pair-subgroups-service-neutral.json).
