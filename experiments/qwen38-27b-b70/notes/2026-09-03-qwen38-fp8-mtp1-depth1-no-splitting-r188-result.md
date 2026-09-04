# R188: the published depth-1 MTP1 profile on the whole-graph compile (`splitting_ops=[]`)

Date: 2026-09-03 20:50-21:14 EDT, boot 88f0984f (clean). Published R156 image unchanged; every server with the
R187 compilation config (`splitting_ops=[]`, lane Inductor config, XPU graphs disabled). Prereg
`data/2026-09-03-qwen38-fp8-r156-mtp1-no-splitting-depth1-r188-prereg.json`; runner
`scripts/run-20260903-qwen38-fp8-r188-depth1-no-splitting-after-r186nb.sh`. Results
`/mnt/fast-ai/bench-results/qwen38-fp8-r156-mtp1-no-splitting-depth1-{strict-20260903-r188a,ladder-20260903-r188b}/`.

| gate | result | published piecewise line (R156) |
|---|---|---|
| G2 MTP1 a vs b (depth 1) | 12/12; 55.006 / 54.865 tok/s class-balanced median | 54.603 |
| G3 vs the R187 same-config MTP0 oracle | 12/12 and 12/12 | 12/12 |
| G5 repeat probe 224/250/300 | ids, logprobs, top-k identical | identical |
| G6 ladder c1-c16 | exact on every rung; aggregate 53.5 / 72.2 / 193.4 / 353.2 / 477.7 tok/s | exact; 51.7 / 77.6 / 173.5 / 352.9 / 474.3 |
| G6 c32 | 31/32 (testing-c013 @34); 810.7 tok/s | 31/32; 798.5 |
| G6 c64 | 59/64 (index-c017 @49, benchmark-c019 @60, cache-c032 @35, index-c033 @33, index-c041 @46); 1063.4 tok/s | 56/64; 1074.1 |

Reading: the whole-graph compile is a drop-in configuration for the published depth-1 profile: same speed
(within server-to-server noise), same identity claim (c1-c16), the same tie-class residual above c16 (the
batch-shape GEMM M-class effect, unchanged as predicted). With R187 (depth 2: strict pairs 12/12 at 70.1 tok/s,
phantom-free sequential pass, MTP0 64/64 through c64), the configuration qualifies both published profiles and
the depth-2 line without a patch or an image rebuild. Whether to move the published line to it, and whether to
publish depth 2 (identity through c4 by the one-miss rule; c8 had one tie-class miss in R187), is the user's
decision; the manifest would change only in the compilation config.

Not done: a second depth-2 ladder to see whether the c8 miss is stable; localisation of the piecewise defect
itself (R186n/R186n-b: last two final-norm rows of the phantom request wrong and rank-divergent).
