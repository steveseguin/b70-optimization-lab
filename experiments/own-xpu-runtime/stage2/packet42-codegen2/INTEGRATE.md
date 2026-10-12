# Integration boundary

This packet prepares candidates. It does not change any current runtime,
scoreboard, package or dispatch. CPU and assembly evidence is not device
qualification. Run K0, T1 and K2 in [WINDOW.md](WINDOW.md) on one admitted card.

The measured output uses the packet26 vocabulary:

```json
{"schema":"packet26.dispatch.v1","classes":{},"gemv":{},"fusions":{}}
```

| Section/key | Candidate | Drop-in submission boundary |
|---|---|---|
| gemv/expsgate | p42.gate.packed | expert_submit.hpp; both IQ2_S and IQ3_S must pass |
| gemv/expsdown | p42.down.select_vector or p42.down.bank_scalar | expert_submit.hpp; IQ4_NL K640 |
| gemv/attention | p42.dense.fourparts | parallel.hpp submit_dense; Q6_K K6144 Split4 production fixture |
| classes/route | p42.route.production_rank32 | route42.hpp submit; four stages replacing five |
| classes/gdn.recurrence | p42.gdn.token1 | parallel.hpp submit; one token and registered flags only |
| classes/tiny runtime key | p42.tiny.range, p42.tiny.wg32, p42.tiny.wg256 | tiny_native.hpp; exact original ng::Shape bindings |
| classes/checks, commits, select, norms, combines, streams | packet42 extras geometry candidates | extras_native.hpp; preserved runtime class keys and bindings |

`p42.route.rank32` on the separate route_gather fixture is diagnostic evidence;
it cannot replace the production adapter route by name. The production route
candidate has its own runtime-incumbent gate and event receipts.

The reshaped tiny entries preserve the current arithmetic body, types,
reduction nodes, BF16 stores, status checks and dependencies. Direct element
leaves can use range or nd_range without the old cooperative scratch/guard
barriers. Cooperative GDN/QSA kernels retain their barriers and local storage;
only the work-item ownership of independent nodes changes. Already-range
classes remain controls and are also measured at alternate work-group widths.
See [inventory](tiny-inventory.md) and the complementary extras source.

The aggregator requires all 200 finite positive GPU and host samples. It sums
all declared events in a group; heavy GEMVs require eight actual distinct
full-payload banks. Output/status bytes must agree with the registered oracle.
A failed case is retained but cannot enter dispatch. Missing formats cannot
qualify a family. Class selection requires at least a 10% improvement over the
matched incumbent; equality/ties retain the incumbent. This is screening, not
model promotion. IQ2 and IQ3 represent 47 and 1 gate groups/token respectively;
other frequencies come from the hash-pinned class-times receipt. Do not sum
mutually exclusive candidates or independent variants for the same class.

Before an integration commit elsewhere, register each new identifier in the
runtime dispatcher, retain existing fallbacks for unsupported shapes, re-run
its argument/alias/lifetime gates, then run full-model output gates and fresh
process repeats. Do not copy this packet's CPU mock dispatch into a runtime.
K2 cannot by itself establish a new full-model speed record.

Norm dispatch is restricted to the measured head count, gain type and flags.
The combined-norm fixture is diagnostic until its gain ABI matches a deployed
site; it cannot stand in for separate norm or combine classes.
