# Packet49d integration map

Build a new packet49d from packet49c only after the coordinator's validated
common selection makes **banked p53b + p54 ≥40 µs in both owners**. Packet54's
independent 25 µs result is reported separately. Never edit packet49c or infer
an integrated model speed from added operator savings. Keep the existing
packet49 oracle and arithmetic identity; no new oracle job is required by
these unchanged-order candidates.

All source references below are relative to `../packet49c-round2/` and are
bound by the control-identity/seal closure. These are exact current call sites;
line numbers can move in the new packet. Adapt standalone headers to the new
packet's local type tree, avoiding duplicate packet45/49c definitions.

## Packet54 candidates

| Class / selection | Exact production call sites | Replacement and preserved bindings |
| --- | --- | --- |
| route-rank4 / route-exp32-rank4 | `main.cpp:1218`, `Engine::execute_site` → `p49c::route`; forwarder `p49c_submit.cpp:35` → selected four-stage `route_submit` | `p54route::submit<4,256>` / `<4,32>` with identical prepared Spec and allocations. Four events, same scratch, BF16 logits, FP32 normalized weights, IDs/descriptors, active/error. Preserve stage0/4 and all existing route extent/alignment/alias admission. |
| rows4-shared / rows8-shared | `main.cpp:1219` → `packet18::submit_parallel`; `adapter.cpp:291` maps `Op::gdn` into ng slots, `adapter.cpp:312` selects `round2::submit`; `dispatch-speed6.json` recurrence=`round2` | Only `blk.L.gdn.recurrence`: `RecurrenceKernel<4>` / `<8>` with `recurrence_bindings`. Four data inputs plus appended active/error inputs, two outputs, two weights; ng slots0/1/2 QKV/a/b,3/4 weights,5 prior state,6 y,7 state,15 error,17 position,18 active. Same BF16 state allocation is input and output. |
| norm-subgroup128 — **closed, do not integrate** | Same generic site path; `adapter.cpp:287` and `specialised_submit.cpp:38` for plain `hc.a.norm` / `hc.f.norm` | `p54hc::submit_norm`, existing prepared ABI and 1280-byte FP32 scratch prefix, two events. Preserve F32 gain, BF16 output, position/active/error. Mix and inject stay production. |
| norm-mix-vector4 — **closed, do not integrate** | Both plain norm sites above plus `adapter.cpp:289` / `ng::mix` for `hc.a.mix` / `hc.f.mix` | Same norm operation plus `p54hc::submit_mix`, one event per mix, exact four-stream ordered sum. Inject stays production. |
| mix-vector4 | `main.cpp:1219` → `adapter.cpp:289` / `ng::mix`, both `hc.a.mix` / `hc.f.mix` | `p54hc::submit_mix`, one event per mix with unchanged four-stream ordered sum. Keep production norm and inject. |
| combine-vector4 — **closed, do not integrate** | `main.cpp:1219`; `adapter.cpp:274` standalone hc_combine → `simple_new_submit`; leaf `adapter.cpp:206` | Rejected by actual-production BF16 NaN mismatch (`7fc0` vs `7fc1`); retain unchanged production. Original proposed `blk.L.ffn.combine`: `p54hc::submit_combine` with same residual/branch/inject/output BF16 bindings. Preserve active/sticky behavior, including its absence of a position check. Preserve layer-end boundary at `main.cpp:1246`. |

The two norm proposals failed actual compiled-production BF16 NaN parity;
their call sites remain listed only as rejected history. Do not integrate them.
Select one eligible common candidate per class or keep its control. HC includes both
sides as one measured class; do not fuse the sides across intervening model
work. Plain norm and combine wrappers explicitly reject fused-combine-norm
ABIs. Retain shape/type/extent/lifetime/alias validation from the production
submission path when integrating recurrence; standalone fixed fixtures are
not a generic runtime API. Keep dependency events and error ownership.

## Banked packet53b winners

The exact [device decision](../packet53b-virtual/evidence-copy/p53b-a-summary.json)
is 23.4385/23.4375 µs. Its 35 µs packet bar failed. The coordinator nevertheless
banks these three exact candidates; HC low/gate and gate/up V16 remain closed.

| Banked class | Exact packet49c call site | Fixed candidate |
| --- | --- | --- |
| Expert gate/up | `main.cpp:1085`, P39 `Engine::linear` branch, `p49b_site` → `p49b::submit` for expert_gate_up | `p53b::GateKernel`, variant2 (`virtual8-split-stream`): IQ2_S K2560,640 rows,10 routes,512 experts; compact820-byte pitch; separate gate/up subgroups. |
| Expert down | Same `main.cpp:1085` for expert down | `p53b::DownKernel`, variant3 (`virtual16-global`): IQ4_NL K640,2560 rows,10 routes; compact360-byte pitch. Keep per-chain K-tail check. |
| Small FFN Q6 tuple | `main.cpp:1054–1062`, small_groups branch, only name=`small.ffn.q6` | `p53b::SmallKernel<4>`: ordered F32 router512, Q6 gate640, Q6 up640, F32 shared-gate1; K2560 split4, original12 w/x/y bindings. Keep `small_followers` skipped. |

Preserve p49b_expert_submit.cpp's route/status/extent/alignment/alias gates,
both expert outputs/statuses, P39 epilogue behavior and sticky controls. Reuse
the existing compact banks; no repacker or additional weight bank is needed.
Preserve packet27 small-tuple validation and exact source activation boundary.
Do not use rejected paired V8/V16 gate bodies or change HC low/gate.
The earlier [p53b map](../packet53b-virtual/INTEGRATION.md) is frozen preparation
history; this document records the subsequent coordinator banking decision.

## Shared integration gates

M1 and each serial M2 row reach the same engine call sites. Recurrence row1
must reload row0's BF16 state. Preserve transaction/rollback, target split23/25,
draft rank1, context4096, model weights, BF16 KV and all unrelated operators.
Prepared command capture reaches these paths too: carry the submitters through
the new build's source mirror and prepared-submission transform, using ranges
visible to the captured wrapper. Do not assume an operator microbenchmark
qualifies captured replay or the full engine.

Packet49d must bind both decision receipts, selected variants and source
hashes; rerun actual production-submitter/engine bytes, controls/positions,
invalid routes, M1/M2 state, prepared capture/replay and fresh-device identity.
Then run matched integrated timing and full-model parity against the existing
completed packet49 oracle. Never replace the 39.422009 tok/s record or promote
a result without those model gates and the separately required publication
attestation/scope. This packet performs no integration or publication.
