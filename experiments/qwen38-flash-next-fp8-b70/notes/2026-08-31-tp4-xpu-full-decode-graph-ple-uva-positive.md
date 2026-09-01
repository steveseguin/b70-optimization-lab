# Qwen3.8 Flash-Next TP4 graph selective-UVA PLE result

Date: 2026-08-31

Status: component positive; full-model graph arm authorized

The exact decode-shape selective-UVA PLE component passed under XPU graph
replay. One graph captured changing global PLE row IDs, rank-local masking,
`index_select` from a pinned-host FP8 table through its XPU UVA view, nonlocal
byte zeroing, and the 5,120-byte TP4 reduction through public oneCCL `4ceafd1`.

All 100 replays on all four ranks matched the CPU-generated FP8 oracle and each
rank produced 100 unique output hashes. The inclusive mean was
`249.82`-`250.64 us/rank`; that includes input generation and copies, device
synchronization, output copies, and CPU oracle work and is not endpoint timing.

This closes the final no-model prerequisite. The graph-aware collective build
has now passed both 97 ordered reductions per graph and the model's unusual
pinned-host PLE lookup path. One full-model candidate is authorized with:

- compilation mode `NONE`;
- `FULL_DECODE_ONLY` and capture size 1;
- public oneCCL `4ceafd1` bound by hash;
- protected untuned MTP0 inference selectors and synchronous PLE;
- the complete semantic, repeat, short-output, 4K needle, and exact-4K battery.

Raw evidence is under
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/20260831-xpu-graph-ple-uva-public-4ceafd1-a4`.
Protected MTP0 `5.515783 tok/s` and MTP4 `20.727176 tok/s` remain unchanged.
