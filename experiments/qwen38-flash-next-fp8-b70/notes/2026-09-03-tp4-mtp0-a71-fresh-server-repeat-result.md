# Qwen3.8 Flash-Next FP8 A71 fresh-server repeat result

Date: 2026-09-03 00:20--00:43 EDT (after the `iommu=pt` reboot; ACS
redirect cleared on all eight B70 root and switch ports for this boot;
GuC 70.72.1 reloaded; card order 43->card0, 47->card2, 23->card3, 27->card4)
Status: every output, quality and speed gate passed and reproduced A70 byte
for byte on an independently started server; the client stopped at the
final runtime-receipt verifier, whose required dispatch table has never
been produced on this line; promotion waits on that receipt, not on the
model

## Gates

| gate | A71 | A70 |
| --- | --- | --- |
| four `mkldnn.deterministic=True` lines, `mkldnn_deterministic=1` receipt | pass | pass |
| recovery canary, runtime identity, twoshots selector, W13-N32 resolver receipt | pass | pass |
| exact semantic cases | 6/7, sole miss `code_execution=30` | same |
| 16-repeat | 16/16, protected `3b0b3192...` | same |
| exact cache-zero 2K needle | pass | pass |
| short rows (after first text) | `22.323215 / 21.498574 / 23.477641 tok/s`, median `22.323215` | `23.028483 / 24.019366 / 22.577949`, median `23.028483` |
| exact-2K rows (99-interval) | `14.207400 / 14.081129 tok/s` | `13.257063 / 13.948739` |
| exact-2K output hash, both rows | **`afffd2110812...`** (candidate pin) | **`afffd2110812...`** |

Two independently started servers of the deterministic graph identity
(full decode graph, public oneCCL twoshots, tuned M1 W13-N32 map,
`VLLM_XPU_MKLDNN_DETERMINISTIC=1`) agree on every output the battery
checks, including the 128-token exact-2K continuation that the native line
could not repeat within one server. The two-attempt short median is
`22.675849 tok/s` against A56's single-attempt `23.626811`; the 2K rows are
above A56's `12.982052 / 12.333460`.

## The stop

After the rows the client runs `verify-q38-a48-fullgraph-runtime.py --phase
after`, which parses the server log for the `--cudagraph-metrics` dispatch
table and requires at least one `FULL` row with one unpadded token. It
raised `no size-1 FULL graph runtime dispatch was recorded`. That table is
absent from every Flash-Next server log on this line: A44 (the certified
graph arm), A55, A56, A70 and A71 all have zero table rows, and none has a
`*-runtime-after.json` or `client-gates-passed.txt`. The server command
carries `--cudagraph-metrics` and the runner builds `CUDAGraphStat` per
step; the table is logged by the API-side stats logger only when
`SchedulerStats.cudagraph_stats` arrives non-empty, so the loss is between
the TP4 multiprocess workers and the API server's stats channel. Graph
dispatch itself is proven by the `Capturing CUDA graphs (FULL)` receipts and
the graph-speed rows.

This is a receipt-plumbing defect in the frozen client lineage, not a
property of A71. Two ways to close it: make `cudagraph_stats` survive the
executor and engine-core stats path (an overlay fix, then a fresh attempt),
or replace the table requirement with the torch-trace graph-replay receipt
the same verifier already collects. Either needs a new attempt to be the
promotion record; nothing protected changes meanwhile.

Receipts: `.../qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp0-2304-ple-only-r1-attempt71/`
and the tracked summary
[`20260903-tp4-mtp0-a71-fresh-server-repeat-summary.json`](../data/20260903-tp4-mtp0-a71-fresh-server-repeat-summary.json).
