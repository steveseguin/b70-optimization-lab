# Ornith 1.5 35B-A3B: attention-gate copy bypass is server-neutral

Date: 2026-08-23 EDT

Status: **CLOSED NEUTRAL — do not ship**

The Qwen-derived attention layers jointly project query and gate values. Each
of Ornith's ten attention layers copies the strided `[256,16]` gate half into a
contiguous 4,096-value buffer; the SYCL backend already fuses the following
sigmoid and attention multiply. A strict decode-only candidate read that gate
view directly in the existing fused arithmetic, removing one `CONT` launch per
attention layer without changing prefill.

The matcher required the exact one-token shape/strides, tensor names, sole-use
three-node chain, contiguous attention operand/output, expected Q/G view offset,
and non-overlapping raw/output storage. It hit exactly 1,270 times in a
128-token run (10 layers × 127 decode steps), and control/candidate canonical
transcripts were byte-identical with SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.

The expanded same-binary engine screen was positive:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `117.001050`, `117.877584`, `116.287503`, `118.446956` | **117.403273** |
| candidate | `117.209415`, `118.625178`, `119.059512`, `119.167630` | **118.515434** |

That is +0.9473%, but the realistic fresh-server mirror did not establish a
stable user-visible win:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `114.025898`, `112.739109` | **113.382504** |
| candidate | `114.288797`, `113.294303` | **113.791550** |

The pooled server difference is +0.3608%. Candidate A beat both controls, but
candidate B lost to control A; process variation exceeded the effect. All
freshness/finality gates passed, making this a valid neutral rather than a
failed run. It is not added to the user package, and canary replay was skipped
after the promotion gate failed.

The incremental source is preserved at
`../patches/llamacpp-ornith15-attn-gate-cont-realistic-neutral-20260823.patch`.
Raw engine/server records, exactness, and the structured conclusion are under
`../data/2026-08-23-ornith35b-attn-gate-cont-*`.
