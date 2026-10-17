# Packet78: route and HC norms

CPU-only candidate preparation copied from frozen packet75 record-bundle
sources. Packet70 production stays `iq3-p49-split32-v1`, wide64 experts,
draft-HC, batch rollback and 24/24 placement. Packet49 remains the device
oracle; KV and target weights are unchanged. No GPU, service or model runs
during preparation.

Five views share one binary: `production`, `route-fast`, `norm-fused`,
`small-combined`, `small+hc-wide`. The last includes packet73's exact HC gate.
The norm-fused name selects the requested single-subgroup alternative; it
does not merge the norm with the low projection.

Route currently launches maximum, exp/sum, rank, and renormalization separately.
The candidate keeps the same max scan, exp polynomial, 16-leaf sums,
denominator tree, rounded probabilities, index tie rule, and selected-weight
normalization. One workgroup replaces all four launches. Integer rank counting
uses two independent candidates per thread and shared probabilities. Its
all-pairs comparisons remain; this trades parallel occupancy for fewer launches
and must be measured. Ranking raw logits would be wrong for rounded ties.

HC norms retain the 80 original 32-leaf FP32 trees, padded 128-root upper
tree, rsqrt, gain and BF16 boundary. Each output tile is now one subgroup;
each lane evaluates original subtrees, followed by the same upper tree.
All scratch partials remain. Packet60 low/activation/injection and packet73
gate/mix semantics are preserved. No whole low projection is duplicated.

Run `cpu_gate.py`, `build_engine.py`, `full_shape.py`, `python_gate.py`,
`seal.py`, `queue_plan.py`, `final_check.py` in that order with nice19,
cores 8-15,24-31, `python3 -B`, stdin `/dev/null`. One compiler at a time;
8 GiB address limit and under 1 GB logical build size. Parent sources and
unchanged objects are hash-bound. Builds never execute device binaries.

The shared v4 wrapper is pinned and used directly. Its placement namespace
requires views below `compat/packet64-record-bundle/selections`; the actual
audit binds packet78 engine sources and binary, never packet64 code.
Lane A runs production, all four candidates, production. Lane B selects only
the exact best lane-A candidate that beats both controls, between two new
controls. Queue proposals are planned only in a temporary directory.

CPU success is not packet49 device parity or a speed claim. The proposed 4%
is a motivation, not a measured result or promise. Device screens and any
subsequent full-chain qualification belong to the coordinator.
