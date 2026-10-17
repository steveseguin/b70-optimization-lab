# Packet49c integration and unchanged arithmetic

Packet49c copies packet49b's source into this new packet. Packet49b, packet49,
packet51 and the running packet49 CPU oracle are read-only inputs. No GPU
program is run during this preparation.

The qualifying input is [packet51's device result](../../../../notes/2026-10-17-own-runtime-packet51-device-result.md)
and its [retained E1/E2/T1/T2 receipts](../packet51-round2/evidence-copy/).
Those timings belong to packet51. Packet49c needs its own early and model
windows; it does not inherit a speed result.

## Selected operators

| Production class | New submission | Preserved behavior |
| --- | --- | --- |
| `route` | Four packet51 route passes | The same exponentials, adjacent sums, rounded probabilities, rank ties, route outputs, global scratch and sticky controls |
| `hc.a.low`, `hc.f.low` | Q8_0 K10240 split4, one workgroup per row | The same four partials, adjacent reduction, BF16 result and activation boundary |
| `hc.a.gate`, `hc.f.gate` | Q8_0 K320 vector-input dense rows | The same lane sequence, adjacent SG32 sum and BF16 output |
| `attention` output plus combine | Q6_K K6144 split4, shared injection factors | The same global partials, BF16 output and four residual streams; two device launches |

`p49c_kernel.hpp` contains only the selected route and dense bodies from the
lab's packet51 candidate. Its local `load32` is the same aligned device load
and host memcpy helper. Header dependencies resolve to this packet's types;
there is no duplicate packet45 runtime type tree. The packet51 IQ2 gate and
GDN QKV candidates are excluded. HC inject, final HC low/gate and all other
classes remain on packet49b's implementations.

`p49c_submit.cpp` retains the existing live allocation, format, shape, extent,
alignment and alias gates. HC low and attention retain the P39 epilogue
validation. The gate-only sentinel is explicitly non-routed and validates
its controls separately. There is no new tensor repack or resident bank.

`Engine::linear` dispatches the HC gate pair before its generic GEMV path,
and dispatches only the HC a/f low pair and attention in its P39 branch.
`Engine::execute_site` selects the new route submitter. These shared paths
are also used while capturing prepared commands, so ordinary decode and both
serial M=2 verification rows reach the same operators. No M=2 batching,
additional bank, scheduling change, precision change or cache reuse is added.

Packet49b's compact IQ2_S expert gate/up, IQ4_NL expert down, and packet49's
split32 QSA are unchanged. The arithmetic identity remains
`iq3-p49-split32-v1`. The same hash-bound packet49 CPU oracle supplies the
full-model reference. Capacity4096, target split23/25, draft rank1, BF16 KV,
weight identity and memory limits stay the inherited ones.

## Gates and limits

`p49c-fixtures` uses actual owner submissions and compares the old submitter
with the new one on the same backend. Its96 cases cover production dense
rows320/10240/2560 and routing, M=1 and each distinct M=2 row, inactive and sticky
controls, invalid positions, dense nonfinite/denormal activations, route ties
and extreme finite logits. It also rejects wrong dense shapes and route
output aliases. Every observed output/control and workspace is compared.

The attention split4 workspace is excluded from the cross-backend canonical
output digest because the existing CPU model does not materialize the device
partial sums. It is still compared byte for byte between old and new paths
on each backend, and the receipt declares this single exclusion explicitly.
All other canonical bytes are retained for the coordinator's CPU/device and
fresh-process checks. This is not a tolerance or an output repair.

`p49c_engine_gate.py` separately compiles a CPU-only adapter against the exact
GNU build objects, excluding the original model entry object. Two fresh
processes run the actual engine's changed dispatch paths over complete
ordinary GDN and QSA layers with deterministic synthetic weights. Each process
covers36 cases (M1 and both M2 rows, six input/control/position cases per
layer), comparing every producer output, logical state and mutable allocation
with explicit packet49b baseline submitters. This adapter uses the legacy
`execute_site` path; prepared-command replay remains covered by the inherited
state/argument gates and fresh device/model windows. Source closure, object hashes,
binary and output hashes are bound in its receipt. This does not replace the
real-model oracle or fresh device gates.

Sanitizer builds retain ASan/UBSan, frame pointers and symbol names. They use
`-g0`, function/data sections and linker garbage collection to remove unused
entry points from each fixture. Sanitizer traces do not carry source-line
debug information; symbols and the hash-bound source identify the failing
function. Production host and device compile flags are unchanged.

Only new packet49c regenerable build scratch may be removed after its gates
and receipt hashes are preserved. Other packets and the oracle remain intact.

The standalone full-layer CPU adapter sets `legacy=true` to compare the actual
`execute_site` paths directly. It is not a qualification of prepared-command
replay or complete MTP scheduling; those remain in the coordinator's device
and model windows. Prepared capture reaches the same selected dispatch paths.
