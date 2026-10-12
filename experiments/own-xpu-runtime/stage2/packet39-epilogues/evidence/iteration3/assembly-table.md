# Offline assembly pairs

Static instruction/message counts. The delta is in the row epilogue owner (the existing finish for split4). One SG32 GEMV covers one row; a finish SIMD32 dispatch covers up to32 independent rows. JSON also gives static delta/row amortized by that geometry, not dynamic counts. It includes alternate finite/exceptional branches and is not a dynamic per-row instruction count or a speed prediction. Every table row has final ELF-text-matched assembly, SIMD, payload and spill metadata in [assembly-review.json](assembly-review.json); work-item wrappers are recorded separately there.

| Class | Unfused GEMV inst/msg | Fused GEMV inst/msg | Row-tail delta inst/msg | Gate |
| --- | ---: | ---: | ---: | --- |
| expert-act-iq2 | 823/31 | 1368/36 | +545/+5 | reject selection |
| expert-act-iq3 | 873/31 | 1416/36 | +543/+5 | reject selection |
| down-status | 1726/58 | 1744/59 | +18/+1 | admit to G4 |
| hc-low-act | 239/10 | 239/10 | +480/+3 | admit to G4 |
| shared-up-act-q6 | 345/21 | 345/21 | +484/+4 | admit to G4 |
| shared-up-act-q8 | 258/11 | 727/15 | +469/+4 | admit to G4 |
| attention-combine | 239/10 | 239/10 | +1761/+13 | admit to G4 |
| shared-down-combine | 418/22 | 2659/39 | +2241/+17 | admit to G4 |
| gdn-qkv-conv-q6 | 258/11 | 781/20 | +523/+9 | reject selection |
| gdn-qkv-conv-q8 | 258/11 | 781/20 | +523/+9 | reject selection |
| expert-checks-iq2 | 823/31 | 842/32 | +19/+1 | admit to G4 |
| expert-checks-iq3 | 873/31 | 893/32 | +20/+1 | reject selection |
