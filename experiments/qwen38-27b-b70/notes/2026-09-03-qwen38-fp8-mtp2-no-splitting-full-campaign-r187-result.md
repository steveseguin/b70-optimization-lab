# R187: R156 + `splitting_ops=[]` (whole-graph Inductor compile), MTP depth 2, full G1-G6 campaign

Date: 2026-09-03 20:02-20:4x EDT, boot 88f0984f (clean). Published R156 image unchanged
(`sha256:173660ec...`); every server of the campaign ran with
`COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],<lane inductor config>}`
(XPU graphs disabled as on the published line, so `cudagraph_mode` is inert). Prereg
`data/2026-09-03-qwen38-fp8-r156-mtp2-no-splitting-full-ladder-r187-prereg.json`; runner
`scripts/run-20260903-qwen38-fp8-r187-no-splitting-full-after-r186.sh`; results
`/mnt/fast-ai/bench-results/qwen38-fp8-r156-mtp2-no-splitting-full-20260903-r187/`.

## Gates

| gate | result |
|---|---|
| G1 same-config MTP0 repeat pair | 12/12; 33.111 / 33.082 tok/s class-balanced median (published piecewise line: 33.314) |
| G2 depth-2 MTP a vs b | 12/12; 70.146 / 70.138 tok/s (R164 piecewise depth-2 pair: 69.94 / 69.38) |
| G3 depth-2 MTP vs regenerated MTP0 oracle | 12/12 and 12/12 |
| G5 repeat probe (224/250/300 tokens) | ids, logprobs and top-k identical on all three |
| G6 depth-2 ladder, sequential 64-prompt oracle pass | **no first-token phantom on any row** (first time at depth 2 with async scheduling on); 4/4 cache-c032 first tokens equal the R156f oracle |
| G6 depth-2 ladder rungs | c1 1/1, c2 2/2, c4 4/4, c8 7/8 (evidence-c007 @13), c16 16/16, c32 31/32 (cache-c000 @96), c64 60/64 (cache-c000 @96, cache-c032 @35, index-c033 @33, cache-c040 @60); aggregate 62.8 / 67.8 / 210.8 / 368.4 / 565.7 / 783.9 / 773.4 tok/s |
| G6 MTP0 ladder | (below) |

The rung misses are the known tie-class prompts at their usual divergence indices (the R67 FP16 tie at
cache-c000 @96, the recurring evidence-c007 @13 and index-c033 @33), the same population and scale as the depth-1
ladders (R156 MTP1: c32 30/32, c64 58/64). They are the batch-shape GEMM M-class effect, not the phantom.

## Reading

With one Inductor graph instead of the default attention/GDN piecewise split, depth-2 MTP on R156 is strict-pair
exact, oracle-exact on the strict suite, probe-exact, and free of the phantom on the ladder's sequential pass, at
70.1 tok/s (vs 69.9 piecewise) and with MTP0 at 33.1 tok/s (vs 33.3, within the 3% server-to-server noise). This is
a configuration change only: no patch, no image rebuild. Depth-2 identity is publishable through c4 by the
one-miss rule (c8 has a tie-class miss); depth-1 published through c16.

Open: the piecewise pipeline's defect itself is still not localised (it needs the default split points and async
scheduling; R186n showed a graph-end op does not remove it while per-layer ops do), and the depth-1 profile's
c32/c64 tie residual is unchanged by this configuration. The depth-1 ladders on the whole-graph compile were not
run in this campaign.
