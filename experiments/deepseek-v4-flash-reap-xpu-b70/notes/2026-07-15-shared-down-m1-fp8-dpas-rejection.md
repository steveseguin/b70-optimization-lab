# Shared-down M=1 ESIMD DPAS feasibility rejection

Date: 2026-07-15

## Question

Could a fixed-shape Xe2 ESIMD kernel replace the production oneDNN W8A8
shared-expert down projection (`M=1, N=4096, K=512`) and save at least
`0.50 ms/token` across 43 layers without changing BF16 output bits?

## Candidate

The feasibility operator transposes the static E4M3FN weight once to `[K,N]`,
loads `16x16` weight tiles, expands E4M3FN to FP16 in registers, and uses Xe2
FP16 DPAS with FP32 accumulation. Four output-tile groupings (`1/2/4/8`) were
screened. This operator is not wired into vLLM and is intentionally exposed
only as a benchmark operation.

The first build accidentally requested every extension and began rebuilding
the generated attention matrix. It was stopped at 632/1298 objects. The useful
incremental command is `ninja -C build/temp _xpu_C`; after the initial target
refresh, source iterations rebuild only the changed object and `_xpu_C`.

## One-card screen

- GPU: Intel Arc Pro B70, affinity rank 0.
- Torch: `2.12.0+xpu`.
- Shape: `M=1, N=4096, K=512`.
- Timing: 5 warmups, 2 alternating batches, 10 calls per batch.
- Correctness: two changed activation/scale epochs.
- Reference: current `_xpu_C.fp8_gemm` oneDNN W8A8 path.
- Scale format in this early screen: FP32 activation and weight scales. This is
  a pre-production feasibility screen; the real checkpoint weight scales are
  E8M0 and would have required a second gate had the candidate survived.

| Tiles/item | Candidate median | Reference median | Speedup | Projected token change | Exact epochs |
|---:|---:|---:|---:|---:|---:|
| 1 | 113.994 us | 48.576 us | 0.426x | -2.813 ms | 0/2 |
| 2 | 180.994 us | 43.623 us | 0.241x | -5.907 ms | 0/2 |
| 4 | 276.853 us | 39.226 us | 0.142x | -10.218 ms | 0/2 |
| 8 | 134.560 us | 38.184 us | 0.284x | -4.144 ms | 0/2 |

The best variant mismatched 1,440 BF16 elements across the two epochs. Maximum
absolute difference was `1.52587890625e-05`; the small error still fails the
bitwise gate required for this quality-sensitive projection.

## Classification

Rejected before four-card, graph-replay, E8M0-scale, or end-to-end testing.
The custom path is 2.35x slower than the same-run reference in its best case
and changes output bits. Software expansion of every FP8 weight byte to FP16
dominates this tiny-M kernel, while the public oneAPI 2025.3 ESIMD DPAS API
does not expose E4M3 operands. This is not a viable production path.

Do not repeat this design by tuning tile counts. A future shared-down attempt
must retain oneDNN's FP8 JIT or use a genuinely native FP8 ISA/JIT path, and
should seek savings through primitive specialization, prepacking, or exact
post-op fusion.

Structured result:
`data/shared-down-m1-fp8-dpas-screen-20260715.json`.

