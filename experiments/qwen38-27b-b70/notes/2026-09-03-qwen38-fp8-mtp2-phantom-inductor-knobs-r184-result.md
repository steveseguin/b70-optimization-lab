# R184: Inductor knobs on the published R156 image, depth 2, async on

Date: 2026-09-03 19:08-19:3x EDT, boot 88f0984f (clean). Prereg
`data/2026-09-03-qwen38-fp8-r156-mtp2-phantom-inductor-knobs-r184-prereg.json`. XPU graphs are disabled on this
lane by default (`XPU Graph is disabled by environment variable`; resolved `cudagraph_mode` NONE), so graph
capture was not an arm. Each arm's override was confirmed in the server's resolved `inductor_compile_config`.

| arm | knob | 64-pass (async on) |
|---|---|---|
| b | `allow_buffer_reuse=false` | phantom on cache-c032 (`[60, 271, 3833]`), 63/64, no other row moved |
| c | `max_fusion_size=1` | phantom on cache-c032, 63/64, no other row moved |
| d | `pattern_matcher=false` | phantom on cache-c032, 63/64, no other row moved (19:26) |

Reading: none of Inductor buffer planning, kernel fusion (at the `max_fusion_size` level) or the pattern matcher
is the mechanism, and none of the three knobs changed a single token elsewhere, so they are numerically inert on
this graph. The
phantom needs the full VLLM_COMPILE pipeline (R183: absent under eager) but not these two Inductor choices.
R185 bisects the compile stack instead (backend=eager under VLLM_COMPILE; DYNAMO_TRACE_ONCE; STOCK_TORCH_COMPILE).
