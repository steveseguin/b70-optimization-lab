# Qwen3.8 Flash-Next TP4 97-collective graph result

Date: 2026-08-31

Status: component positive; no model load or reboot

One `XPUGraph` containing 97 independent ordered BF16 `[1,2560]` reductions
was replayed 100 times through public oneCCL `4ceafd1`. Every rank and every
buffer changed before each replay. All 9,700 outputs per rank matched the exact
CPU sum, and each rank produced 100 unique composite hashes.

The inclusive mean was `19.751`-`19.756 ms` per graph, or
`203.62`-`203.67 us` per collective. These figures include input generation
and copies, full device synchronization, 9,700 CPU oracle constructions and
output copies, and hashing; they are diagnostic rather than endpoint timing.

This passes the collective cardinality and ordering prerequisite for one
target token. The remaining no-model prerequisite is the actual selective-UVA
FP8 PLE lookup at decode shape with changing row IDs. Only after that passes
may a size-1 `FULL_DECODE_ONLY` endpoint arm be frozen.

Raw evidence is under
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/20260831-xpu-graph-xccl-public-4ceafd1-97sequence-a3`.
Protected MTP0 `5.515783 tok/s` and MTP4 `20.727176 tok/s` are unchanged.
