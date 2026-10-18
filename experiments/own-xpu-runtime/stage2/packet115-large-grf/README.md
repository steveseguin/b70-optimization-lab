# Packet115: expert-only LARGE register images

CPU preparation only. All four exact designs pass the 256-GRF zero-spill gate.
No GPU measurements or model speed claims are made by this packet's preparation.
The device micro and v5 bracket require separate coordinator admission.

| Kernel choice | Mechanism | Source |
| --- | --- | --- |
| `production` | Packet103 half-cache gate/up and tile16 down | Packet103 after103x |
| `e3-next` | Next-block IQ2 table reads | Packet95 rejected next-block copy, adapted to half-cache |
| `iq4-bytepair` | Exact IQ4 byte-pair SLM lookup | Packet99 copy, adapted to tile16 addresses |
| `v4-batch2-shared` | Batch two IQ2 lookups while sharing gate/up inputs | Packet102 V4 combined copy |
| `e5-shared` | V8 shared gate/up inputs, independent sums and trees | Packet102 V8 scheduling adapted for E5, common output epilogue |

Frozen source copies and exact adaptation details: [kernels](kernels/README.md).
Production always uses tile16 down; no old row-layout down baseline is substituted.
Candidate runs use LARGE for both directions, using unchanged LARGE production
for the direction the candidate does not change.

`libp115_normal.so` and `libp115_large.so` are separately linked SYCL AOT images
for BMG-G31. Only expert entry kernels are emitted there (plus the compiler's
symbol-table entry). Namespace separation prevents default/LARGE kernel-ID
coalescing and collision with the parent runtime's production kernels.
The remaining runtime retains its inherited allocation mode. The option is
module-wide `-ze-opt-large-register-file`, not a per-kernel SPIR-V property.

The [linked image report](evidence/images.json) binds each image, source,
assembly and Zebin metadata. Every admitted entry has no scratch allocation,
no scratch load/store instructions and no flag spills. Default reports 128 GRFs;
LARGE reports 256. E5's first output epilogue spilled predicate flags even at
256; [its original source and report](evidence/e5-first/) are retained. The
common epilogue removes these without changing its FP32 chains or tree.

The [CPU byte gate](evidence/cpu-byte-identity.json) uses GNU and Intel, twice
per view. It checks full outputs, status/error bytes, exceptional inputs,
partial/invalid routes, all raw FP32 chains and trees, and exhaustive decode
cases. CPU equality is independent of device equality and speed.

## Coordinator micro

[Two proposed B jobs](../../ops/lane-queue/proposed-p115-micro-B.txt) each use
a fresh process. Budget 180 seconds each, watchdog 900 seconds; actual duration
is unmeasured. Each runs all 384 preregistered packet100b route vectors, both
orders, and both default and LARGE production controls. The actual expert
output/status/control bytes must match. Weights and activations are synthetic;
the captured expert IDs are real. Each measured kernel gets an equal 512 MiB
device scrub. This is an operator diagnostic, not a model benchmark.

The candidate must use at most 85% of each control's time in each order in
both processes, using medians of matched-route ratios. No route is selected
based on time. Individual ratios stay diagnostic because there is only one
pair per order per route. The [gate](micro_gate.py) rechecks raw rows and every
source, binary, route, process and drain binding before v5 admission.

## CPU rebuild

Use `nice -n 19 taskset -c 8-15,24-31 python3 -B` with stdin `/dev/null`:
`probe.py`, `build_images.py`, `build_cpu.py`, `route_inputs.py`,
`build_microbench.py`, `test_micro_gate.py`, then `queue_plan.py`.
Compilation uses packet94's shared lock. CPU caps apply only in CLI processes.
After source changes, repeat affected gates and reseal; never mutate a proposed
binary while the coordinator is using it. Root free must stay at least 25 GB;
the entire packet's build storage is capped at 250 MB.

Parallel v5 preparation is conditional on the micro. It retains
the unchanged model-output oracle `iq3-p49-split32-v1`, one model load, strict
layout invariance and fresh control/candidate/control transitions.

[Work note](../../../../notes/2026-10-18-own-runtime-packet115.md).
