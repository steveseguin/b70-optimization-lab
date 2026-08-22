# TP1 z-row cold-weight verdict: kernel geometry innocent; tax = per-activation quantize

Date: 2026-08-22

Status: diagnostic; no timing here is promotable. Instrument:
[cold-weight GEMV bench](../scripts/qwen38_tp1_cold_gemv_bench.cpp)
(ten rotated q8_0 weight copies per graph, working sets 266-903 MiB >>
L2, chained negligible adds), lane build libs, GPU0, run while USB
downloads were active (coarse-verdict tolerance; the signal is ~40%,
not ~1%).

## Measurements (cold weights, standalone)

| Shape | us/call | GB/s | In-graph (profile note) |
|---|---:|---:|---:|
| z-row [6144, k=5120] q8_0 | 62.36 | **536.7** | 87.7 us, 381.7 GB/s |
| sibling [10240, k=5120] q8_0 | 99.80 | 558.8 | 102.5 us, 543 GB/s |
| square [5120, k=5120] q8_0 | 52.92 | 527.1 | — |
| ffn-out-shape [5120, k=17408] q8_0 | 167.18 | 567.0 | — |

## Verdict

1. **Rung 3 closes: the m=6144 kernel geometry is healthy** (within 4%
   of its sibling cold). The 381.7 GB/s in-graph figure is a
   graph-context effect, not a kernel property.
2. **The tax is per-activation quantization + launch gap.** In-graph,
   all 48 z inputs are distinct activations: one q8_1 quantize kernel +
   its dispatch gap lands inside every MUL_MAT window (~25 us on a
   62 us op, ~40%). In this bench the ten GEMVs share one activation,
   so the lane's Q8 memo dedups the quantize to ~0.1/call — which is
   precisely why the bench streams clean. The sibling's smaller
   in-graph excess (~16 us on a 103 us op) fits the same fixed-cost
   model.
3. This unifies rung 2 and rung 3 into one target: **the per-call
   activation-quant overhead in the in-order queue**, coherent with the
   profile note's ~240 hidden quantize launches per graph.

## Routing (design work, not tonight)

- The direct fix family (producer-side Q8 emission) was already
  **rejected for exactness** on this route
  (`q8out-rejected` note: icpx fp-model=fast per-TU codegen divergence
  makes byte-exact cross-TU quantizer replication impossible).
- Remaining honest directions, each needing design: (a) a second
  in-order queue overlapping the quantize of the next consumer with the
  current GEMV, preserving byte-identical kernels and order per tensor
  (needs a correct event-dependency graph — nontrivial); (b) reducing
  dispatch gap (command-list batching of quant+GEMV pairs); (c) a
  documented non-bit-exact speed door (forbidden for promoted results
  under the lane standard; page-lane relevance only if ever).
- Estimated pool if fully recovered: z alone ~1.2 ms/token; the
  fixed-cost model across mid-size rows suggests roughly 2-3 ms/token
  total, i.e. the bulk of the 27.8 -> 30 gap. It is real but gated on
  runtime-level design, not a shape widening.
