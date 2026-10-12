# Kernels available per class

This is the closed dispatch vocabulary compiled into packet29. Availability is
not device qualification or a speed claim. Arithmetic identity v2 applies to
the inherited finite GEMV contract; see NONFINITE-GEMV.md.

## classes

| Class | Available entries |
| --- | --- |
| `hc.a.norm` | `packet18`, `specialised` |
| `hc.f.norm` | `packet18`, `specialised` |
| `final.norm` | `packet18`, `specialised` |
| `ple.kn` | `packet18`, `specialised` |
| `ple.qn` | `packet18`, `specialised` |
| `ple.cn` | `packet18`, `specialised` |
| `gdn.norm` | `packet18`, `specialised` |
| `gdn.recurrence` | `packet18`, `specialised`, `round2` |
| `qsa.prepare` | `packet18`, `specialised` |
| `qsa.pool` | `packet18`, `specialised` |
| `qsa.select` | `packet18`, `specialised`, `round2` |
| `qsa.attention` | `packet18`, `specialised`, `round2` |
| `attn.combine` | `packet18`, `specialised` |
| `ffn.combine` | `packet18`, `specialised` |
| `route` | `packet18`, `specialised`, `round2` |
| `gather` | `packet18`, `specialised` |
| `argmax` | `packet18`, `specialised`, `round2` |
| `streams` | `packet18`, `specialised` |
| `ple.add` | `packet18`, `specialised` |
| `norm` | `packet18`, `specialised` |

## gemv

| Class | Available entries |
| --- | --- |
| `expsgate` | `r5`, `p25.rows4`, `p25.wg32`, `p25.private_decode`, `p25.paired_input`, `p25.half_table`, `p27.fp32_input`, `p28.private.rows4`, `p28.private.wg32`, `p28.shared.rows4`, `p28.shared.wg32`, `p28.paired.rows4`, `p28.paired.wg32` |
| `expsdown` | `r5`, `p25.rows4`, `p25.wg32`, `p25.private_decode`, `p25.wide8`, `p27.packed64`, `p27.rows2sg`, `p27.fp32_input`, `p28.private.rows4`, `p28.private.wg32`, `p28.shared.rows4`, `p28.shared.wg32`, `p29.down.wg32`, `p29.down.rows4` |
| `gdn.qkv` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `gdn.z` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `qsa.qgate` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `qsa.k` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `qsa.v` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `attention` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `ple.key` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `ple.value` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `hc.a.gate` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `hc.a.low` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `hc.a.inject` | `r5`, `p28.dense.rows4`, `p28.dense.wg32` |
| `hc.f.gate` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `hc.f.low` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `hc.f.inject` | `r5`, `p28.dense.rows4`, `p28.dense.wg32` |
| `final.gate` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `final.low` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `qsa.iq` | `r5`, `p28.dense.rows4`, `p28.dense.wg32` |
| `qsa.ik` | `r5`, `p28.dense.rows4`, `p28.dense.wg32` |
| `router` | `r5`, `p28.dense.rows4`, `p28.dense.wg32` |
| `gdn.a` | `r5`, `p28.dense.rows4`, `p28.dense.wg32` |
| `gdn.b` | `r5`, `p28.dense.rows4`, `p28.dense.wg32` |
| `shexpgate` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `shexpup` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `shexpdown` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `shared_gate` | `r5`, `p28.dense.rows4`, `p28.dense.wg32` |
| `logits` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `hc.gate` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |
| `hc.low` | `r5`, `p25.rows4`, `p25.scale8`, `p25.wide8`, `p27.packed64`, `p27.fp32_input`, `p28.dense.rows4`, `p28.dense.wg32` |

## fusions

| Class | Available entries |
| --- | --- |
| `attn.combine+norm` | `packet18`, `specialised` |
| `ffn.combine+norm` | `packet18`, `specialised` |
| `route+gather` | `packet18`, `specialised`, `round2` |
| `small.hc` | `packet18`, `round2` |
| `small.gdn.ab` | `packet18`, `round2` |
| `small.ffn` | `packet18`, `round2` |
