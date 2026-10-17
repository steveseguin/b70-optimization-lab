# Packet49d integration map (winners pending)

Do not edit packet49c. After a passing two-owner packet53b decision, build a
new packet49d from the complete packet49c-round2 sources. Read
`selected_classes` in the verified summary: `control` means keep the current
path; otherwise use exactly its one common V. There are no winners yet.
The arithmetic identity and packet49 CPU oracle stay unchanged.

All paths below are in `../packet49c-round2/`. Line references identify the
current source; the packet53b seal binds these integration inputs by hash.

| Measured class | Exact engine call to replace | New operation and bindings |
| --- | --- | --- |
| expsgate | `main.cpp:1085`, `Engine::linear`, `p49b_site(...) ? p49b::submit(...)` for `expert_gate_up` | `p53b::GateKernel`, V from decision. Keep paired output ABI with IQ2_S K2560, rows640, count10, experts512; same compact banks, BF16 x and both outputs, routes, both statuses, error, active |
| expsdown | Same `main.cpp:1085` P39 branch for expert down | `p53b::DownKernel`, selected V, IQ4_NL K640, rows2560, count10; preserve per-slot x, output/status and sticky controls |
| hc.low_gate low members | `main.cpp:1084–1085`, `round2` for `hc.a.low`/`hc.f.low`, calls `p49c::dense_submit`; shape selection `p49c_submit.cpp:29` | `DenseKernel<Q8_0,10240,4,V,silu_div4>`, rows320. Preserve BF16 output, `b.out` activation, context/position/active/error and original silu/div4 boundary |
| hc.low_gate gate members | `main.cpp:1088–1090`, explicit `hc.a.gate`/`hc.f.gate` branch | `DenseKernel<Q8_0,320,1,V,expert_checks>`, rows10240. Same V as both low members. No epilogue; preserve bound controls |
| small.ffn.q6 | `main.cpp:1054–1062`, `small_groups` branch, only `name=="small.ffn.q6"` | `SmallKernel<V>` with the original ordered four members: F32 router512, expanded Q6 gate640, expanded Q6 up640, F32 scalar shared-gate1; all K2560 Split4; one launch, original 12 w/x/y bindings |

Keep `p49b_expert_submit.cpp`'s shape, compact format, extent, alignment,
route and alias checks when adding the new expert submitter. Keep
`p49c_submit.cpp`'s dense validation, position checks and live bindings when
adding the HC submitter. Keep `packet27::small::validate` for the tuple and
its ordering; do not route small.ffn.q8 or mini fixtures into this path.
The packet53b standalone kernels are benchmark bodies, not replacements for
those production admission checks.

`Engine::prepare_small_groups` (main.cpp around 693–715) builds the tuple;
`small_followers` remain skipped so outputs are written exactly once. Preserve
its grouping and source activation boundaries. HC low/gate remains four
sequential sites across the attention and FFN sides. Do not fuse across the
attention/FFN work between those sides. The screen groups their durations for
selection only. HC final low/gate, HC inject, route, attention output, QSA,
GDN, shared down and all other classes keep packet49c's implementations.

M=1 and M=2 use these same call sites. M=2 means two serial production rows;
there is no batch-shape dispatch or new two-row bank. Preserve the transaction,
rollback, target split23/25, draft-rank1, context4096, weight and BF16 KV
identities. Selected V changes only the distribution of logical lane chains.

Prepared command capture reaches the same `linear` paths. Carry the new
submitter through `build.py`/`CMakeLists.txt` and the prepared-submission source
mirror so capture and ordinary launches use the same specialization. Follow
packet49c's literal/outer-scope launch-range handling rather than relying on
an inner local constant that the prepared wrapper cannot capture. The selected production tuple control is `p30.small.rows4` from the dispatch-speed6
manifest (the packet27 tuple supplies the same shape declaration). Keep event
and allocation lifetimes, validation and dependencies intact.

Adapt the new kernels to packet49d's local types/header tree (as packet49c did
in `p49c_kernel.hpp`); do not include packet45's adapter types alongside a
second engine tree. Reuse the compact expert bytes exactly; no new repacker,
weight bank, intermediate global buffer or tensor precision change is needed.
HC uses 4V local floats; all padding lanes still reach the barrier. Expert
down retains its per-chain K check. V4 gate/up retains paired input sharing; V8/V16 split gate/up across subgroups.
Select the registered split-stream body, not the rejected paired V8/V16.
Expert compact row pitches remain exactly820/360 bytes.

Before model windows, repeat production submitter/engine byte fixtures at M1
and both M2 rows, active/error/position and invalid-route cases, prepared
capture/replay gates, and fresh device output identity. Bind winners, the
packet53b performance decision and register report to packet49d. Use the
existing packet49 oracle for full-model parity. A packet53b operator pass
is not full-model qualification and does not replace packet49d's gates.
