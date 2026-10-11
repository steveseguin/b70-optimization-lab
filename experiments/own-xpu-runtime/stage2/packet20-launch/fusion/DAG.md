# Dependency DAG: actual packet18 sites

Generated from plan.cpp plus packet18 expert_gate_up normalization. Inputs include controls; each edge is a named buffer dependency. Shared streams/history/state writes are read-after-write and write-after-read lifetime edges.

## Layer 0: GDN

| Site / operation | Inputs | Outputs |
| --- | --- | --- |
| hc.a.norm / norm | streams, active, error | hc.a.norm |
| hc.a.low / gemv | hc.a.norm, active, error | hc.a.low |
| hc.a.act / silu_div4 | hc.a.low, active, error | hc.a.act |
| hc.a.gate / gemv | hc.a.act, active, error | hc.a.gate |
| hc.a.mix / hc_mix | hc.a.norm, hc.a.gate, active, error | hc.a.mix |
| hc.a.inject / gemv | hc.a.norm, active, error | hc.a.inject |
| gdn.qkv / gemv | hc.a.mix, active, error | gdn.qkv |
| gdn.z / gemv | hc.a.mix, active, error | gdn.z |
| gdn.a / gemv | hc.a.mix, active, error | gdn.a |
| gdn.b / gemv | hc.a.mix, active, error | gdn.b |
| gdn.conv / conv | gdn.qkv, gdn.history, active, error | gdn.conv, gdn.history |
| gdn.recurrence / gdn | gdn.conv, gdn.a, gdn.b, gdn.state, active, error | gdn.y, gdn.state |
| gdn.gated / gdn_norm_gate | gdn.y, gdn.z, active, error | gdn.gated |
| attention / gemv | gdn.gated, active, error | attention |
| attn.combine / hc_combine | streams, attention, hc.a.inject, active, error | streams |
| hc.f.norm / norm | streams, active, error | hc.f.norm |
| hc.f.low / gemv | hc.f.norm, active, error | hc.f.low |
| hc.f.act / silu_div4 | hc.f.low, active, error | hc.f.act |
| hc.f.gate / gemv | hc.f.act, active, error | hc.f.gate |
| hc.f.mix / hc_mix | hc.f.norm, hc.f.gate, active, error | hc.f.mix |
| hc.f.inject / gemv | hc.f.norm, active, error | hc.f.inject |
| router / gemv | hc.f.mix, active, error | router |
| route / route | router, active, error | ids, prob |
| gather / expert_gather | ids, hc.f.mix, active, error | routes, routes.down, expert_input |
| expsgate / expert_gate_up | expert_input, routes, active, error | expsgate, expsgate.status, expsup, expsup.status |
| expsgate.check / check_status | expsgate.status, error, active | error |
| expsup.check / check_status | expsup.status, error, active | error |
| expsact / silu_product | expsgate, expsup, active, error | expsact |
| expsdown / routed_gemv | expsact, routes.down, active, error | expsdown, expsdown.status |
| expsdown.check / check_status | expsdown.status, error, active | error |
| shexpgate / gemv | hc.f.mix, active, error | shexpgate |
| shexpup / gemv | hc.f.mix, active, error | shexpup |
| shexpact / silu_product | shexpgate, shexpup, active, error | shexpact |
| shexpdown / gemv | shexpact, active, error | shexpdown |
| shared_gate / gemv | hc.f.mix, active, error | shared_gate |
| moe / moe_combine | expsdown, prob, shexpdown, shared_gate, active, error | moe |
| ffn.combine / hc_combine | streams, moe, hc.f.inject, active, error | streams |

## Layer 3: QSA

| Site / operation | Inputs | Outputs |
| --- | --- | --- |
| hc.a.norm / norm | streams, active, error | hc.a.norm |
| hc.a.low / gemv | hc.a.norm, active, error | hc.a.low |
| hc.a.act / silu_div4 | hc.a.low, active, error | hc.a.act |
| hc.a.gate / gemv | hc.a.act, active, error | hc.a.gate |
| hc.a.mix / hc_mix | hc.a.norm, hc.a.gate, active, error | hc.a.mix |
| hc.a.inject / gemv | hc.a.norm, active, error | hc.a.inject |
| qsa.qgate / gemv | hc.a.mix, active, error | qsa.qgate |
| qsa.k / gemv | hc.a.mix, active, error | qsa.k |
| qsa.v / gemv | hc.a.mix, active, error | qsa.v |
| qsa.iq / gemv | hc.a.mix, active, error | qsa.iq |
| qsa.ik / gemv | hc.a.mix, active, error | qsa.ik |
| qsa.prepare / qsa_prepare | qsa.qgate, qsa.k, qsa.iq, position, active, error | qsa.q, qsa.gate, qsa.kn, qsa.iqn |
| qsa.pool / qsa_append_pool | qsa.kn, qsa.v, qsa.ik, position, qsa.raw, active, error | qsa.keys, qsa.values, qsa.raw, qsa.pooled |
| qsa.select / qsa_select | qsa.iqn, qsa.pooled, position, active, error | qsa.ids |
| qsa.attention / qsa_attention | qsa.q, qsa.gate, qsa.keys, qsa.values, qsa.ids, active, error | qsa.y |
| attention / gemv | qsa.y, active, error | attention |
| attn.combine / hc_combine | streams, attention, hc.a.inject, active, error | streams |
| hc.f.norm / norm | streams, active, error | hc.f.norm |
| hc.f.low / gemv | hc.f.norm, active, error | hc.f.low |
| hc.f.act / silu_div4 | hc.f.low, active, error | hc.f.act |
| hc.f.gate / gemv | hc.f.act, active, error | hc.f.gate |
| hc.f.mix / hc_mix | hc.f.norm, hc.f.gate, active, error | hc.f.mix |
| hc.f.inject / gemv | hc.f.norm, active, error | hc.f.inject |
| router / gemv | hc.f.mix, active, error | router |
| route / route | router, active, error | ids, prob |
| gather / expert_gather | ids, hc.f.mix, active, error | routes, routes.down, expert_input |
| expsgate / expert_gate_up | expert_input, routes, active, error | expsgate, expsgate.status, expsup, expsup.status |
| expsgate.check / check_status | expsgate.status, error, active | error |
| expsup.check / check_status | expsup.status, error, active | error |
| expsact / silu_product | expsgate, expsup, active, error | expsact |
| expsdown / routed_gemv | expsact, routes.down, active, error | expsdown, expsdown.status |
| expsdown.check / check_status | expsdown.status, error, active | error |
| shexpgate / gemv | hc.f.mix, active, error | shexpgate |
| shexpup / gemv | hc.f.mix, active, error | shexpup |
| shexpact / silu_product | shexpgate, shexpup, active, error | shexpact |
| shexpdown / gemv | shexpact, active, error | shexpdown |
| shared_gate / gemv | hc.f.mix, active, error | shared_gate |
| moe / moe_combine | expsdown, prob, shexpdown, shared_gate, active, error | moe |
| ffn.combine / hc_combine | streams, moe, hc.f.inject, active, error | streams |
