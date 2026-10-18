# Packet109 lane B screen

Run one rank pair with production/fused/production/fused/production selections,
one initial weight load and a complete native request reset at every boundary.
The only changed selection field is `other_fusion`; all draft choices, target
weights, arithmetic, layout, KV precision and the oracle remain fixed.

Each view runs the incident64 check followed by the twelve fixed prompts at
128 generated tokens. Require 8,000 exact oracle token comparisons across the
five views, zero cached tokens, unchanged per-prompt speculative acceptance,
complete boundary/reset receipts and no weight upload after the initial load.
A failure stops the screen and retains its evidence. The inherited supervisor
uses cooperative shutdown and fault monitoring; it does not restart a failed
rank pair.

The question is whether the complete engine benefits from 72 fewer launches
per target half. Report both candidate timings against all three controls,
control drift, TTFT and request/decode timings. A mean-only improvement is not
a win; the report's strict comparison requires both candidate views to beat
every control. Retain per-prompt results. No microbenchmark estimate is a
performance result. This one-load screen is diagnostic; promotion would still
need the lane's independent fresh-server quality and performance requirements.

Lane B uses the existing private two-card mapping and lane ownership/drain
protocol. Expected runtime is at most 900 seconds including loading, prompts,
boundaries and teardown. The supervisor watchdog is 3,600 seconds (4×). The
proposal is planned in a temporary queue directory. It does not edit or enqueue
into either live queue, and CPU preparation does not execute a GPU program.

Inputs: [fixed bracket](configs/bracket.json), [production selection](lineage/selection.json),
[fused selection](lineage/candidate.json), [memory plan](lineage/memory-plan.json),
[native seal builder](seal_native.py), [wrapper seal builder](cpu_seal.py).
