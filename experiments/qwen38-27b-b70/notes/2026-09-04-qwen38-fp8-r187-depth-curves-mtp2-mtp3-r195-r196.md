# R195/R196: 2K-32K real-content depth curves for MTP depth 2 and depth 3 on the R187 line

Date: 2026-09-04 00:49-01:01 EDT, boot 88f0984f (clean). R156 image, `splitting_ops=[]`, same protocol and the
same same-configuration MTP0 oracle as R189 (three real-content classes, three requests per depth, 128 output
tokens, cache zero, canaries). Results `data/2026-09-04-qwen38-fp8-r187-mtp{2,3}-real-content-depth-r19{5,6}-result.json`.

Both depths matched the MTP0 oracle on 18/18 complete arrays.

| active context | MTP0 (R189) | depth 1 (R189) | depth 2 (R195) | depth 3 (R196) | depth-3 TTFT |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 33.00 | 54.61 | 70.85 | 80.60 | 0.60 s |
| 4096 | 32.74 | 55.17 | 73.37 | 83.61 | 1.17 s |
| 8192 | 31.90 | 53.74 | 70.98 | 84.71 | 2.37 s |
| 16384 | 31.18 | 52.68 | 68.97 | 77.86 | 4.94 s |
| 24576 | 30.45 | 51.56 | 60.16 | 66.87 | 7.74 s |
| 32768 | 29.78 | 51.55 | 68.53 | 83.19 | 10.73 s |

Reading: the depth gain holds across the whole context range (depth 3 stays above depth 2 above depth 1 at every
point except the 24K depth-2 sample, a three-request median on one content mix); TTFT is the same prefill cost for
all profiles. Depth 3 is the fastest lossless single-user profile at every measured depth.
