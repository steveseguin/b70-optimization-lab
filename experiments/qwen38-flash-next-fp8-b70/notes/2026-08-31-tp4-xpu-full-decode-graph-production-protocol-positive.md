# Qwen3.8 Flash-Next TP4 production-protocol graph result

Date: 2026-08-31

Status: component positive; no model load or reboot

The corrected A/B found a concrete collective repair. At the protected
endpoint's `CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096`, the current endpoint libccl
passed eager execution and graph replay 0, then mismatched on replay 1 on all
four ranks. The public oneCCL `4ceafd1` build passed all 100 changing-input
replays on all four ranks, with 100 unique exact output hashes per rank and an
identical eager/graph hash series.

The public build's graph mean was `313.94`-`314.86 us/rank`; the deliberately
fully synchronized eager oracle was `4455.51`-`4455.90 us/rank`, a diagnostic
`14.15`-`14.19x` ratio. This timing includes per-iteration input copies, device
synchronization, CPU oracle construction, and output copies, so it is neither
an isolated collective latency nor an endpoint forecast.

The current library's failure at both `8192` and `4096`, together with exact
success from the graph-recording build at `4096`, identifies the library's
replay sequencing rather than the production collective protocol as the
blocker. The next bounded prerequisites are:

1. 97 independent ordered BF16 `[1,2560]` reductions in one graph, matching a
   target step's collective count;
2. exact changing-row selective-UVA PLE lookup under graph replay;
3. only after both pass, one size-1 `FULL_DECODE_ONLY` endpoint arm with the
   complete protected quality battery.

Raw A/B evidence is under
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/20260831-xpu-graph-xccl-{current-963-threshold4096,public-4ceafd1-threshold4096}-a2`.
The structured result is
[`20260831-tp4-xpu-full-decode-graph-production-protocol-positive.json`](../data/20260831-tp4-xpu-full-decode-graph-production-protocol-positive.json).

Protected MTP0 `5.515783 tok/s` and MTP4 `20.727176 tok/s` remain unchanged.
