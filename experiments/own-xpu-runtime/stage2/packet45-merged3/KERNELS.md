# Packet45 merged kernels

Arithmetic remains `iq3-p17-detmath-v2`: original adjacent reduction
nodes, split-four finish tree, BF16 stores and full 16-bit cache. The values below
are prior card measurements of standalone groups, not a packet45 model speed.
K1 tests the merged submit paths; fresh K2 chooses from them. No performance
claim is closed on CPU.

| Class | Integrated option | Prior measured saving, ms/token |
|---|---|---:|
| route | p42.route.production_rank32; four owner events instead of five | 1.220016 |
| routed expert gate/up | p42.gate.packed, IQ2 and IQ3; selectable K2 candidate | 0.235521 |
| GDN gated norm | p42.tiny.wg256 (`gdn.norm` / `gdn.gated` aliases) | 0.052524 |
| GDN recurrence | p42.gdn.token1 | 0.045 |
| attention residual combine | p42.extras.combine.wg32 | 0.039984 |
| FFN residual combine | p42.extras.combine.wg32 | 0.039984 |
| QSA prepare | p42.tiny.wg256 | 0.033744 |
| QSA select | p42.extras.select.wg256 | 0.026244 |
| HC attention activation | p42.tiny.range | 0.020016 |
| HC FFN activation | p42.tiny.range | 0.020016 |
| QSA pool | p42.tiny.wg256 | 0.018756 / 0.017508 across retained cases |
| final HC activation | p42.tiny.range | 0.000417 |
| routed gate/up + both status checks IQ2/IQ3 | p39.epilogue | about 0.31; 71.3/76.2 ->64.6/69.9 us/group |
| down + status | p39.epilogue | about 0.14; 96.9 ->94.0 us/group |
| attention projection + residual combine | p39.epilogue | about 0.22; 63.6 ->59.2 us/group |
| HC low + activation | p39.epilogue | about 0.18; 19.1 ->17.2 us/group |
| shared up + activation Q6/Q8 | p39.epilogue | about 0.12; 16.0/18.5 ->13.5/14.7 us/group |
| shared down + blend + combine | p39.epilogue | about 0.11; 27.1 ->24.7 us/group |

Sources: [packet42 card2 table](../packet42-codegen2/receipts-card2-20261012/table.md)
and [packet39 card3 G4 receipt](../packet39-epilogues/receipts-card3-20261012-g4/README.md).
Values from overlapping options must not be added. In particular p39 removes
HC activation/combine launches that p42 can accelerate separately. Packed gate
and checks fusion are alternative GEMVs; a selected packed gate keeps both
original checks. No new unmeasured packed-gate-plus-checks kernel is invented.

The p39 plan transform physically removes superseded launches and retains their
raw outputs/status buffers. Shared gate moves before shared down; the existing
ordered ten-expert mixture remains its own owner compute before shared down.
Shared down inherits the old `.ffn.combine` label so layer snapshots, cancellation,
streaming release and the final-stream handoff still run at the layer boundary.
Split-four attention remains two separately registered owner compute calls. Every
actual launch therefore retains argument ownership, cancellation and event hooks.

QSA selector uses packet44's `extent` in both work-group count and scratch bounds.
Only independent leaf ownership changes. No capacity, position validation, tie
ordering or valid-prefix behavior comes from the older packet42 capacity code.

K2 compares exact outputs and 200 complete event sequences. Classes whose measured
incumbent cost exceeds 2 ms/token use 3%; remaining classes use 10%. Both IQ2 and IQ3
must pass. A missing format, lost event, zero/invalid timestamp or wrong incumbent
cannot admit a candidate. K2 timings and full-model quality remain independent.

## Excluded dense.fourparts: why CPU passed

The actual card failure is retained in
[dense-fourparts-device-failure.jsonl.gz](dense-fourparts-device-failure.jsonl.gz):
`attention.gdn`, mode 0, candidate arm 1, row 1 expected BF16=17234 and actual 65472.
It failed twice (the two timing modes); it was never admitted.

[parallel_submit.cpp](../packet42-codegen2/parallel_submit.cpp) computes its row
stride as `6144 + 4*6144/group`, omitting the source-format metadata retained by
[expanded::row_bytes](../packet10-kopt5/expanded.hpp). Q6 K6144 rows are 8112 bytes,
not 7680; Q8 rows are 7296, not 6912. Row 0 begins correctly; row 1 starts 432/384 bytes
too early, so it reads metadata as the next row's codes/scales and can produce NaN.

[parallel_cpu.cpp](../packet42-codegen2/parallel_cpu.cpp) allocates one shortened
row and compares `dense_parts` lane arithmetic against the incumbent on that same
row. It never executes the native multirow addressing or checks the expanded
allocation layout. This is a layout coverage hole, not evidence that the card
changed arithmetic. Packet45 has no dense.fourparts registry entry, submit code,
or attempt to qualify it. Any future related candidate must test the actual
expanded multirow buffer and native row address calculation before device work.

The merged p39 CPU helper exercises 56 byte comparisons (eight chains, seven
control/nonfinite scenarios), including the real owner submit calls and complete
unfused tails. Each compared snapshot contributes its length and SHA256 to the
fixture output identity. The capacity receipt requires all 56 scenarios. CPU
registration and K2 admission tests cover 72 cases. Per-token gate cost weights
IQ2/IQ3 by 47/1 layers; alternative QSA lengths use the maximum measured workload
cost rather than summing lengths that do not coexist in one token.

The first merged GNU K1 exposed a real integration conflict: at context 256,
position window 136, the copied p42 pool code placed its cache-append group at
`capacity/4`, beyond packet44's newly-completed-pool launch. Output slot 4 stayed stale.
The merged code uses `append_pools(s)` and offsets each pool group by `pos/4`, retaining packet44's
capacity behavior. The failed attempt remains in the capacity gate failure archive.
All three capacity arithmetic gates must pass on this correction before sealing.

The merged CPU gate also exercised the legacy GDN `flags=1` fixture. Token-one
selection now masks the unrelated bit 0 before choosing its specialization;
weight encoding, decay and packed-head bits 1–3 remain unchanged. This is an
admission correction, with no change to the GDN row equations.

K2 additionally times the three production HC activation classes (`hc.a.act`,
`hc.f.act`, `final.act`) at 320 BF16 values with the actual `silu_div4` adapter.
Each has its own 200-repeat comparison and dispatch key. If its p39 producer
fusion is declined, K2 retains a qualifying p42 range activation on the remaining
launch. Four actual adapter cases cover finite, inactive, sticky-error and NaN
inputs against both incumbent and p42 owner submissions.
