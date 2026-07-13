# Next Xe2 boundary: GDN QKVZ and output projections

Date: 2026-07-13

Status: measured design target; implementation should begin after the guarded
Q6_K draft top-1 A/B completes

## Why this boundary is next

The warmed M=6 target operation census shows that the remaining recurrent
projection families dominate the visible matrix-multiply work after the FFN
gate/up and most FFN down tensors moved to the Xe2 path:

| Family | Graph-13 timed work | Calls |
|---|---:|---:|
| GDN output | 7,297 us | 48 |
| GDN QKV mixed | 3,880 us | 48 |
| GDN z | 3,663 us | 48 |
| GDN alpha + beta | 3,808 us | 96 |

The operation timer serializes the graph, so these values rank work but are not
production wall time. Even with that caveat, the boundary is much larger than
the exact SwiGLU-to-Q8 tail, whose realistic isolated estimate was only
0.16-0.44 ms/cycle.

## Exact model types and shapes

Inspection of the promoted Q4_0 GGUF establishes the actual ABI:

| Tensor | Shape | GGUF type | Per-layer bytes |
|---|---:|---:|---:|
| `attn_qkv.weight` on GDN layers | 5120 x 10240 | Q4_0 | 29,491,200 |
| `attn_gate.weight` (z) | 5120 x 6144 | Q4_0 | 17,694,720 |
| `ssm_alpha.weight` | 5120 x 48 | F32 | 983,040 |
| `ssm_beta.weight` | 5120 x 48 | F32 | 983,040 |
| `ssm_out.weight` | 6144 x 5120 | Q5_K | 21,626,880 |

There are 48 GDN layers. The existing full187 pack intentionally covers FFN
gate/up and eligible Q4_0 FFN down tensors; it does not cover these GDN shapes.
The alpha/beta and Q5_K output paths also cannot use the current Q4_0 DPAS ABI.

## Staged implementation

### A. Joint Q4_0 QKV + z

Generalize the existing M=6 offline pack and DPAS producer to the 5120-input
QKV and z shapes. The two projections share exactly the same normalized input,
so produce canonical Q8_1 once and submit a heterogeneous dual-output kernel
or one command group over both packs. Do not concatenate or reorder semantic
outputs in the model graph.

Start with one captured real layer, then all 48. The added packed-weight
footprint is about 2.26 GB if all QKV and z packs are resident, so the smoke
test must record device headroom before full integration. Reuse the trusted RAM
pack-cache format rather than rebuilding packs on every server start.

### B. Joint exact F32 alpha + beta

The two 48-wide matrices share the same 5120-wide input and together contain
only 96 outputs per layer. Fuse them into one exact F32 kernel/submission that
reads the input once and writes two independent outputs. Quantizing these
weights would change the model and is not part of the exact baseline lane.

This stage is launch- and input-read-oriented. Reject it if the full target
cycle does not improve; the raw weight traffic is only about 94 MB across all
48 layers and therefore cannot explain a multi-millisecond bandwidth win by
itself.

### C. Q5_K GDN output + residual

Build a separate M=6 Q5_K verifier specialization for 6144 x 5120 and attach
the residual epilogue only after the projection kernel wins in isolation. The
prior generic M=1 GDN-output epilogue was neutral; that result does not validate
or reject a native M=6 Q5_K projection. Account for the added resident pack
before selecting an expanded-i8 or denser native Q5 layout.

## Gates

1. Real captured tensors must match the production numerical contract and
   preserve fixed-request token IDs and DFlash acceptance exactly.
2. The joint QKV/z microbenchmark must beat the exact production pair by at
   least 1.30x at M=6 before runtime integration.
3. Each integrated stage must save at least 2 ms per representative production
   cycle or improve the same-build cold suite by at least 3%. Otherwise retain
   the experiment but leave it default-off.
4. A full-resident pack configuration must leave enough headroom for target,
   F16 draft KV, DFlash weights, Q6 top-1 pack, and runtime scratch. A faster
   kernel that makes the production context unstartable is a failed lane.
5. Promotion still requires the fixed strict cold/cached-zero gates. Favorable
   code results are tracked separately and cannot replace the mixed-suite
   record.

## Architectural consequence

This is the first step toward hipfire's transferable QKVZA concept, adapted to
the actual GGUF types instead of copied as an AMD/MQ4 assumption. On this model
the correct Intel boundary is heterogeneous: Q4_0 QKV/z, exact F32 alpha/beta,
and Q5_K output. The useful fusion is shared activation production, grouped
submission, and exact epilogues; a single monolithic kernel is not required.

