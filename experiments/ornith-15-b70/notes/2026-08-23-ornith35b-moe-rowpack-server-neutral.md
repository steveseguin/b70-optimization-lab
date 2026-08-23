# Ornith 1.5 35B-A3B: routed-MoE row packing is server-neutral

Date: 2026-08-23 EDT

Status: **CLOSED SERVER-NEUTRAL/SLIGHT-NEGATIVE — do not ship**

Ornith's Qwen-derived routed expert gate/up and down kernels originally place
one independent 32-lane output-row subgroup in each SYCL workgroup. A
default-off geometry candidate packed 2, 4, or 8 row subgroups into each
workgroup without changing any row's weight reads, accumulation, subgroup
reduction, or FP32 output store.

Both the selected two-row geometry and the aggressive eight-row geometry
produced the canonical forced 128-token transcript SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
The selected run retained all 5,080 routed gate/up and 5,080 shared
residual/RMSNorm hits.

The initial 1/2/4/8 engine ladder selected two rows per workgroup. A subsequent
mirrored `1/2/2/1` engine test passed its separation gate:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| one-row control | `119.631285`, `121.352565` | **120.491925** |
| two-row candidate | `121.472751`, `121.738769` | **121.605760** |

That is **+0.9244%**, with both candidates above both controls. It did not
survive the required fresh-server test:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| one-row control | `118.237295`, `117.271192` | **117.754244** |
| two-row candidate | `117.385602`, `117.731584` | **117.558593** |

The serving result is **-0.1662%**. Both candidates lost to control A, so the
candidate fails the promotion rule. Every freshness and final-response gate
passed; this is a valid neutral/slight negative, not a malformed run.

The incremental source is preserved at
`../patches/llamacpp-ornith15-moe-rowpack-server-neutral-20260823.patch.gz.b64`;
decode with `base64 -d | gzip -dc` before applying.
Raw ladder, mirrored engine, fresh-server records, and the structured summary
are under `../data/2026-08-23-ornith35b-moe-rowpack-*`. The accepted package
remains unchanged.
