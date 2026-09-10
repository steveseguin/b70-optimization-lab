# The 32-row FP16 linear chunk is a throughput tax, and a class-consistent pad removes it

Evening of 2026-09-09. Data: `data/2026-09-09-qwen35-4b-fp16-linear-chunk-tax.json`; probes in `probes/`;
image patch `experiments/qwen38-27b-b70/docker/r290-fp16-linear-classpad.py`.

## How it was found

Chain 10's `x2` mapped the no-speculation throughput dip at every rung between c32 and c64 with every rung
graph-captured: 1593 tok/s at c32, 1253 at c36, then a straight recovery to 1727 at c64. Padding to a captured
shape was eliminated by construction. The one thing in the server with that shape was the R224 overlay,
which runs every unquantized FP16 linear - the vocabulary projection and the MTP `fc` - in pieces of at most
32 rows: above 32 sequences the last piece holds 4, 8, 12, 16, 24 then 32 rows, and throughput tracked it.

`y1` reran x2's rungs with the chunk disabled. The prediction was right about the cause and wrong about the
size. The dip is not a partial last piece. Every piece re-reads the whole weight, and at this model's
vocabulary the weight is 248320 x 2560 fp16 = 1.2 GB. So depth 3 at c32 - 128 rows, four pieces - was
already paying 41%, and c64 - 256 rows, eight pieces - 54%. No-speculation pays 25-30% above 32 users:

| rung | MTP0 chunk 32 | MTP0 chunk 0 | depth 3 chunk 32 | depth 3 chunk 0 |
| --- | ---: | ---: | ---: | ---: |
| c32 | 1593 | 1646 | 1153 | 1626 |
| c36 | 1253 | 1623 | 1102 | 1602 |
| c48 | 1508 | 1904 | 1190 | 1781 |
| c64 | 1727 | 2162 | 1201 | 1850 |

That tax sits under every throughput figure this lane published above eight users at depth 3 - the c16
speculation ceiling, the "depth 3 stops scaling" reading, the depth plateau, the TP2 matrix - and under
every no-speculation rung above c32. The published exact rungs (16, 32, 64, 96, 128) happen to sit where
the no-speculation cost is zero or smallest, which is why the shape was never obvious.

## But the chunk is not an identity null

With the chunk off, MTP0 divergence at c32-c64 goes from under 1% to 11-15% - including at c32, where a
32-row call and a single 32-row piece should be the same GEMM. They are not the same path: with the chunk
off the projection is lowered by `torch.compile` instead of running as the opaque eager op, and that path
is not row-invariant at any M. So "turn it off" buys throughput at the price the chunk was bought to avoid.

## The census

`probes/fp16-linear-mclass-census.py` and friends run eager `F.linear` at the real shape on one card and
compare bits. The oneDNN fp16 GEMM has four M-classes at this shape - rows 1-32 (bit-identical to the
single-row result), 33-128, 129-320, 321-512 - and within every class the result is **position-invariant,
pad-invariant and deterministic**: roll the rows and un-roll, or zero-pad the batch, and every real row's
bits are unchanged. A 32-row call costs 2.24 ms, a 256-row call 2.88 ms, a 512-row call 4.5 ms: the GEMM is
bandwidth-bound on the weight, and eight 32-row pieces cost 17.8 ms against 2.88 for one call.

The transposed layout (`x @ W^T` with the weight stored K x N) is no better: its first class boundary is at
32, so M=32 already leaves the single-row class, and it is slower.

## R290: keep every call in one class

If rows are invariant within a class, the single-row class is not special. R290 extends the R224 op: on
first use of each weight shape it measures the class of row 0 for M = 1..512, picks the most populous class
as canonical, and pads every smaller call with zero rows to the next canonical size or splits a larger one
into pieces no bigger than the largest canonical size. For the TP1 vocabulary shape that means a single-row
call runs as 33 rows (2.23 ms against 2.12) and a 256-row call runs as one 321-row call (3.05 ms against
R224's 17.8). One user and sixty-four then compute bit-identical rows. Offline, for the TP1 and TP2
vocabulary shapes and the `fc` shape, every M from 1 to 600 is bit-identical to the 128-row reference and to
64 single-row calls, and deterministic.

Off by default; `VLLM_XPU_FP16_LINEAR_CLASSPAD=1` turns it on, and both launchers now forward it. The op
logs its measured map once per shape (`R290 classpad census ...`), so a container's `server.log` records
what it did. Chain 13 (`p1`-`p9`) measures it on the server: identity ladders and the strict gates on both
topologies, the stagger recipe on the fragile suite, the high rungs, and depths 2 and 4.

## What this does not say yet

Offline exactness is not the ladder. The ladder against the sequential oracle is the claim, and until `p1`
and `p5` report, R290 is a validated kernel-level property and a prediction: MTP0 near-exact as with R224,
the stagger recipe still 1280/1280, and depth 3 up 40-50% above c16. The TP2 shard's canonical class is
129-320, so on two cards a single-row call pads to 129 rows (1.22 ms against 1.08); if the strict gate
notices, the choice of canonical class can be made by cost rather than by population.

`run-server.sh`, the no-speculation path, did not forward `VLLM_XPU_FP16_LINEAR_ROWCHUNK` until this evening
(it now does, including 0); the MTP0 servers in every previous arm ran the patched code's default of 32.
