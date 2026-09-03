# Qwen3.8 Flash-Next FP8 A82 preregistration: eager MTP1 on the deterministic line

Date: 2026-09-03
Status: frozen before launch; diagnostic arm that separates the graph from
the speculative path

## Question

A81 (MTP1 inside the full decode graph) reproduced the MTP0 line's short
p146/o256 output exactly at 38.5-44.0 tok/s, but its exact-2K continuation
diverged from the MTP0 line's `afffd211...` at token 7 (a near-tie: `"branch":
"main"` versus `"branch": "A"`, both well formed; 13 of 128 tokens
coincide) on both rows, and decoded there at 6.9-7.3 tok/s with 100-147 s
TTFT against the MTP0 line's 14 tok/s and 47-58 s. Is the depth divergence a
property of the speculative verification path (the two-row verify step
runs the GDN spec-decode kernel and M=2 GEMMs whose summation order differs
from the single-row decode) or of replaying that step from the captured
size-2 graph?

## Design

`tools/rewrite-q38-a66-to-a82-eager-mtp1.py` derives A82 from the frozen
eager deterministic packet A66 (`--enforce-eager`, mkldnn deterministic,
public oneCCL twoshots, tuned M1 W13-N32 map, PLE-only UVA) with the A74
capacity change (4352), the A80 MTP change (`MTP=1`, 376,569,856 KV bytes,
base freeze lifted to exactly 1), the A79 storage change (NVMe copy, 256 GiB
read cap) and the A81 memory floor (12 GB). No graph. The frozen client is
renamed for hash pinning only; `a82-diag-driver.sh` runs the same battery
as A81 against the same pinned MTP0 hashes. Attempt 82 / port 19754.
Packet: launcher `17760673...`, client `95bdbb43...`, supervisor
`04a7a7a5...`, host wrapper `7dfe5813...`.

## Reading

- Eager MTP1 matches the MTP0 hashes at 2K/4K: the graph replay of the
  size-2 step is what breaks exactness at depth; a graph-side fix is the
  next target.
- Eager MTP1 also diverges at 2K (same or different hash as A81): the
  speculative verification path is not bit-exact against single-row decode
  on this model, independent of the graph; MTP on Flash-Next then needs the
  serial-exact treatment the 27B FP8 lane applied (serial spec attention,
  serial GDN gates, M-invariant GEMM paths) before it can be lossless.
- Depth rates and TTFT of eager MTP1 against A81 also show whether the
  depth slowdown belongs to the graph or to the speculative path.
