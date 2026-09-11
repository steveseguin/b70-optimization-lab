# R293 on the 27B INT4 lane: the FP16 linear pieces were a small tax here, and the recipe transfers

2026-09-11, R295-R298, chain `scripts/run-20260911-qwen38-int4-r295-r298-classpad-chain.sh`, entries
`R295_*`, `R296_*`, `R297_*`, `R298_*` in `data/2026-09-05-qwen38-int4-graph-capture-tp2-mtp4-r247-result.json`.
Mechanism, census and the R290-R293 history: `experiments/qwen35-4b-b70/notes/2026-09-09-the-fp16-linear-chunk-is-a-throughput-tax.md`
and `experiments/qwen35-4b-b70/notes/2026-09-11-r293-class-consistent-fp16-linear-on-the-server.md`.

## What was measured

The served configuration (R276 code path: TP2, depth 4, capture sizes to 320, INT4 draft head, pad off) on the R293
image with `VLLM_XPU_FP16_LINEAR_CLASSPAD=1`, verified in every container by the op's own census line. R295 is a full
run: a fresh MTP0 pair (G1), a depth-4 pair gated against its own MTP0 (G2, G3), then two-pass c1-c64 ladders on both
profiles. The stored eager R239 oracle that R283 gated against is a different rounding class under R293 (the projection
now runs in the 129-320-row class on the TP2 shard) and is not the reference for this image.

| | R276 | R293 |
| --- | ---: | ---: |
| depth 4 strict pair | 112.90 / 113.00 (R283) | 111.69 / 111.33, G2 12/12, G3 12/12 x2 |
| MTP0 strict pair | 49.83 / 49.89 (R253) | 49.39 / 49.39, G1 12/12 |
| depth 4 warm pass c8 / c16 / c32 / c64 | 422.6 / 578.9 / 634.5 / 589.0 (R282) | 436.1 / 611.1 / 682.6 / 627.8 |
| depth 4 identity c16 / c32 / c64 | 16/16, 30/32, 60/64 | 16/16, 30/32, 59/64 |
| MTP0 warm pass c32 / c64 | 815.8 / 989.8 | 815.4 / 1019.2, exact c1-c64 |
| big admission MTP0 c64 / c128 / c256 | 1032.8 / 966.8 / 1021.3 (R290) | 1067.4 / 1010.7 / 1079.5 |
| big admission depth 4 c64 / c128 | 591.4 / 584.7 (R284) | 637.1 / 647.7 |
| MTP0 c64, 5 ms stagger, ten passes | - | 640/640, output-identity-qualified, 1014.4 |

## Reading

The gain is 3-8% on the speculative lane from c8 up and 3-6% without speculation from c64 up, at a 1% single-user
cost, with identity unchanged at every rung. That is the expected size: the 2.5 GB projection is a small share of a
19 GB model whose decode step is dominated by the dequant-bound INT4 GEMMs, so removing one weight read per 32 rows
saves about 40 ms of a ~380 ms step at c64 depth 4. On the Qwen3.5 4B and 9B, where the projection is the largest
tensor, the same switch is worth 25-56%. The R224 pieces stay the right *identity* mechanism only in the sense that
R293 keeps the same op and the same invariance; the pieces themselves were never necessary.

The staggered-admission recipe (`--launch-stagger-ms 5`, found on the 4B) ran here for the first time: 640 of 640
concurrent outputs across ten passes byte-identical to the sequential oracle, harness-certified. The published two-pass
64/64 becomes a ten-pass claim at a 1% throughput cost.

Not changed: the many-user ceiling (about 1080 tok/s at c256 without speculation) is the INT4 GEMM; the big-admission
identity profile (exact to c32, 5-9% divergent from c64 under a 4096-token admission budget) is as R284/R290 found it.
