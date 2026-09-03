# Qwen3.8 Flash-Next FP8 A81 result: MTP1 inside the full decode graph

Date: 2026-09-03 10:28--10:52 EDT
Status: **diagnostic; exact and 1.7x faster at short context, not exact and
slower at 2K/4K**; not a record

## Server

The A80 packet with the supervisor memory floor at 12 GB: deterministic
graph identity (overlay `2169dbfe`, mkldnn deterministic, public oneCCL
twoshots, tuned M1 W13-N32 map, PLE-only UVA), NVMe model copy, 4352 tokens,
`--speculative-config {"method":"mtp","num_speculative_tokens":1}`,
`cudagraph_capture_sizes` [1, 2] (one FULL graph captured, the two-token
verification step, plus the speculator's graph), KV 376,569,856 bytes
(9,284 tokens). Weights 66 s; ready 8 minutes after launch; minimum
`MemAvailable` during the battery about 16 GB (the MTP0 line: 20.5 GB).

## Battery against the MTP0 line's pinned hashes

| gate | A81 (MTP1, graph) | MTP0 line (A73/A78/A79) |
| --- | --- | --- |
| short p146/o256 rows (after first text, tok/s) | **`38.791200 / 44.022386 / 38.532635`**, median `38.79` | `22.26-24.73`, center `22.66` |
| short output hash | `5f407446...` on all three rows | same |
| exact semantic cases | 6/7, normalized outputs identical | same |
| 16-repeat | 16/16 `3b0b3192...` | same |
| exact cache-zero 2K needle | pass | pass |
| exact-2K rows (99-interval tok/s; TTFT s) | `7.253414 / 6.912107` (146.6 / 99.8) | `13.44-14.91` (47-58) |
| exact-2K output hash | `460b0d5c...` on both rows | `afffd211...` |
| exact-4K rows (99-interval tok/s; TTFT s) | `7.610711 / 7.620807` (166.1 / 151.4) | `12.24-13.50` (89-103) |
| exact-4K output hash | `bf25b9d1...` on both rows | `c6193cc6...` |
| draft acceptance over the battery | 733 of 787 draft tokens (93%) | |

The 2K continuation diverges at token 7, a near-tie inside the JSON fixture
(`"branch": "main"` on the MTP0 line, `"branch": "A"` here; 13 of 128
tokens coincide afterwards, both texts well formed). A81 is self-consistent
(both rows of each depth share one hash), so the speculative path is
deterministic too; it is a different function from single-row decode at
depth.

## Reading

- At short context MTP1 is bit-exact against the MTP0 line over three
  256-token rows, seven quality cases, the 16-repeat and the 2157-token
  needle, and raises decode from 22.7 to 38.8 tok/s (1.71x) with 93% draft
  acceptance. That is the headroom on the table.
- At 2K and 4K the verification step's logits are not those of single-row
  decode: the two-row step runs M=2 GEMMs and the GDN spec-decode kernel
  whose summation order differs from the M=1 path, and the fixture's
  near-ties expose it. Under the lab's lossless standard this line is not
  promotable at depth. The 27B FP8 lane hit the same class of problem and
  fixed it kernel-side (serial spec attention R38, serial GDN gates R50,
  M-invariant GEMM paths); Flash-Next needs the equivalent in its GDN
  spec-decode and MoE paths.
- Depth is also slower with MTP1 than without (7 vs 14 tok/s at 2K, 2x the
  TTFT), so even a lossy MTP1 would not help beyond a few hundred tokens of
  context on this line. A82 (eager MTP1) tells whether the graph replay or
  the speculative path owns the divergence and the slowdown.

Receipts: run dir `...attempt81/`, tracked
[`diagnostic`](../data/20260903-tp4-mtp1-a81-graph-mtp1-diagnostic.json).
Preregistrations: A80, A81 (memory floor).
