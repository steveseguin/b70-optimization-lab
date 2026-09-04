# R198: full-decode XPU graph capture on the whole-graph compile is lossless and slower on this host

Date: 2026-09-04 01:23-01:46 EDT, boot 88f0984f (clean). R156 image, `splitting_ops=[]`, `VLLM_XPU_ENABLE_XPU_GRAPH=1`,
`cudagraph_mode=FULL_DECODE_ONLY`. Prereg `data/2026-09-04-qwen38-fp8-r187-graph-capture-r198-prereg.json`.

| profile | capture sizes | graph on (a / b) | graph off (published) | delta | identity |
|---|---|---|---|---|---|
| MTP1 | [1,2] | 54.182 / 54.133 tok/s | 54.935 | -1.4% | 12/12 vs sibling and vs the R187 MTP0 oracle |
| depth 3 | [1,2,3,4] | 78.245 / 78.292 tok/s | 79.183 | -1.2% | 12/12 vs sibling and vs the oracle |

Reading: same as R58 (piecewise, size 1) and R163 (piecewise, [1,2]): on this EPYC host per-launch submission is
cheap enough that graph replay's fixed cost outweighs it, whole-graph or piecewise. Graph capture stays off on the
published line here; it remains the right setting for slower hosts (four-B70 host: 1.77x, R139 replay).
