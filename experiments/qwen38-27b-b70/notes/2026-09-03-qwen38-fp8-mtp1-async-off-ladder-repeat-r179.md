# R179 (MTP1 half): depth-1 ladder with `--no-async-scheduling` repeated on a fresh boot

Date: 2026-09-03 17:48-17:55 EDT, boot 88f0984f (clean pre/post). Image R156 (`sha256:173660ec...`), same config as
R175 (`EXTRA_SERVE_ARGS=--no-async-scheduling`, LADDERS_ONLY). Results:
`/mnt/fast-ai/bench-results/qwen38-fp8-r156-mtp0-async-off-ladder-20260903-r179/ladder/ladder.json`.

| rung | R175 (10:xx) | R179 (17:5x) |
|---|---|---|
| c1-c16 | exact | exact |
| c32 | 32/32 | 29/32 (rollback-c010 @97, testing-c013 @34, benchmark-c019 @60) |
| c64 | 61/64 (evidence-c047 @85, rollback-c050 @60, evidence-c063 @88) | 58/64 (cache-c000 @96, evidence-c007 @13, index-c033 @75, testing-c045 @28, evidence-c047 @85, rollback-c050 @60) |

Aggregate tok/s within 3% of R175 at every rung (c64: 1053 vs 1020). Both runs are classified
`output-isolation-qualified-shape-variant`; neither is publishable above c16.

Reading: async-off is not a stable depth-1 fix. The miss set moves between runs on the identical server config
(only two prompts recur: evidence-c047 @85, rollback-c050 @60), and cache-c000 @96 is the R67 exact FP16 tie. This is
the census-known M-class / run-to-run GEMM nondeterminism at large M, not the depth-2 phantom mechanism. Do not
re-gate async-off ladders as a fix; the depth-1 residual above c16 stays with the MTP draft-forward census.

## R179 (MTP0 half, 17:55-18:03): the ladder R175 lost to the GPU fault

`ladder-mtp0/ladder.json`: c1-c32 exact, c64 63/64 (index-c041 @46). Aggregate tok/s equals the published
async-on R156f run at every rung (c64 931.4 vs 931.4). R156f async-on was 64/64 at c64. Async-off therefore
gives MTP0 nothing (one extra miss, within the same large-M variance seen on MTP1) and costs nothing; the published
MTP0 async-on identity claim stands. Do not spend more servers on `--no-async-scheduling` ladders for either depth-1
profile; it matters only for the depth-2 phantom (R169), which is a separate mechanism.
