# Laguna INT4 tile-record locality preregistration

Date: 2026-07-31 America/Toronto

Status: **closed at the first static gate**. No GPU component, model load, or
scored endpoint run occurred.

## Premise

The exact width-12 target streams each K32 x N64 packed-INT4 tile and its 64
BF16 scales on every grouped-GEMM traversal. The protected scale transpose
proved that physical metadata locality matters (+2.42% for W13+W2), but the
weights still use checkpoint `[N,K/2]` storage while the kernel traverses
`[N64,K32]` tiles.

The existing MXFP4 kernel already supports immutable tile records. Generalize
that mechanism for INT4 without changing a packed nibble or BF16 scale:

```
[1024 untouched INT4 weight bytes][128 untouched BF16 scale bytes]
```

per N64 x K32 tile. Arithmetic, K order, DPAS shape, BF16 scaling, and output
rounding remain identical. Only immutable physical layout and load addresses
change.

## Gates

1. Matched BMG AOT probe must compile with GRF128, identical DPAS/arithmetic
   counts, and no new spills. Reject a clearly worse final ISA.
2. A one-device W13+W2 component must compare at least three changed BF16
   inputs bitwise against the protected transposed-scale route. Require a
   repeatable component improvement of at least 4%; this route carries enough
   integration and memory risk that a sub-noise result is not actionable.
3. Before model integration, quantify persistent memory. Prefer replacement
   over duplication; if decode-only duplication is required, prove it fits
   without reducing the protected KV/cache/graph contract.
4. Only after those gates: exact endpoint leg with the frozen 13-prompt corpus,
   146/145 target and 14/13 draft topology, cache-zero, and normal scored
   window. No graph/capture work may be moved outside scoring.

The protected 125.461973 conventional tok/s BF16-KV record remains unchanged
until every gate passes.

## Static result

The generalized tile-record kernel compiled at GRF128 and preserved the
arithmetic body: both forms contain 2 DPAS and 33 multiplies in the matched
K256 probe. It nevertheless failed the instruction gate decisively:

| physical layout | final BMG instructions | delta |
| --- | ---: | ---: |
| protected ordinary weights + transposed scales | 370 | control |
| N64/K32 INT4+BF16 tile records | 468 | +98 (+26.5%) |

The blocked record required extra source-region and address materialization
inside the K traversal. The existing tile-major source reconstructs the packed
tile tensor/copy view around each dynamic K record; IGC could not fold that
machinery into the protected affine block-copy path. The unchanged arithmetic
does not compensate for a 98-instruction control/address increase, so gate 1
rejects the route before timing.

Artifacts:

- source commit: `7af3f6204f` on
  `experiment/laguna-int4-tile-record-20260731`;
- static dump:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-tile-record-20260731T061354`;
- patch snapshot:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-probe-INT4-tile-record-locality.patch`.

Generic lesson: co-locating immutable weights and metadata is not enough when
the physical layout makes the compiler rebuild a blocked view in the hot
loop. A future tile-record attempt needs an affine/hierarchical tensor layout
constructed once outside the K traversal; this implementation must not be
timed or promoted as-is.
