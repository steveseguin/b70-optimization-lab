# GDN QKVZAB folded-gate hot-module result

Date: 2026-07-13

Status: hot-module microbenchmark gate passed; protected runtime integration
not started

## Result

The candidate covers the four real layer-0 projections sharing the 5120-wide,
six-row input:

- Q4_0 QKV, `5120 x 10240`;
- Q4_0 z, `5120 x 6144`;
- F32 alpha, `5120 x 48`;
- F32 beta, `5120 x 48`.

It produces Q8_1 once, then launches one heterogeneous ESIMD command group.
The Q4 groups retain the active strided eight-way DPAS reduction order. The F32
groups use 32-wide ESIMD vectors and exact F32 weights. A second guarded
operation folds the alpha downstream sequence `alpha + ssm_dt`, stable
softplus, and multiplication by `ssm_a`; the six rows execute in parallel after
the alpha workgroup reduction. QKV, z, folded gate, and raw beta remain separate
semantic outputs.

Two repeatable, warmed, 100-iteration runs on an otherwise idle B70 measured:

| Boundary | Run 1 | Run 2 |
|---|---:|---:|
| Active QKV + z + beta + alpha | 143.440 us | 143.309 us |
| Joint QKVZAB | 99.407 us | 99.457 us |
| Projected 48-layer saving | 2.114 ms | 2.105 ms |
| Active four projections + alpha add/softplus/mul | 147.737 us | 147.768 us |
| Joint QKVZAB with folded alpha gate | 99.247 us | 99.237 us |
| Projected 48-layer folded saving | 2.328 ms | 2.329 ms |

The folded result clears the required 2 ms projected-cycle gate with about
0.33 ms margin. It does not yet prove a 3% cold-suite improvement because no
runtime graph was changed.

## Correctness

- QKV and z are bit-exact against the actual integrated M=6 symbols.
- Alpha versus oneMKL: max abs `0.000010`, max rel `0.000006`.
- Beta versus oneMKL: max abs `0.000004`, max rel `0.000004`.
- Folded downstream gate versus active oneMKL plus separate elementwise
  sequence: max abs `0.000002`, max rel `0.000001`.
- A bad `ssm_dt` layout is rejected before any queue submission.

ESIMD lacks `log1p`; the folded producer uses the same stable softplus identity
as production, `max(x,0) + log(1 + exp(-abs(x)))`, with a final-rounding
difference measured above. Promotion still requires fixed-request token and
DFlash acceptance equality using a real internal GDN input capture.

The current fixture is a genuine model-generated M=6 final-norm activation,
not layer-0's internal GDN input. This does not affect the arithmetic or timing
comparison, but it is insufficient for downstream token promotion.

## Pack and headroom accounting

- Per-layer production pack: `49,152,384` bytes.
- All 48 GDN layers: `2,359,314,432` bytes (`2.197 GiB`).
- Workspace: `38,400` bytes per active launch.
- Comparator device global memory: `34,242,297,856` bytes.
- Bare-card free memory before the comparator: about `34.148 GB`.
- The one-layer comparator allocation reduced reported free memory by about
  `115.6 MB`; this includes both candidate and oracle copies and outputs.

The full 48-layer production footprint is plausible on a 32 GiB B70, but the
required target + DFlash + KV + Q6-pack headroom must be measured in the actual
server before enabling every pack. The runtime plan should support a pack limit
and fail closed before model startup exhausts memory.

## Rejected four-output grouping

An F32 variant grouped four alpha/beta outputs per workgroup to share each input
vector load. It reduced the F32 group count from 96 to 24 and increased register
state. The result regressed to `122.791 us` versus the `145.153 us` active
sequence, projecting only `1.073 ms` across 48 layers. Restoring one output per
workgroup and increasing its ESIMD vector width from 16 to 32 produced the win.
The exact rejected source delta is retained in
`patches/qwen27-gdn-qkvzab-f32-joint4-rejected-20260713.patch`.

## Matcher and integration handoff

Implement a graph-prepass plan rather than trying to coordinate four independent
`MUL_MAT` dispatches:

1. Match TP1, M=6, no-LoRA, non-split Qwen GDN layers with Q4_0
   `attn_qkv.weight` and `attn_gate.weight`, F32 `ssm_alpha.weight` and
   `ssm_beta.weight`, and one identical contiguous F32 input pointer.
2. Verify exact shapes, model content tag, exclusive alpha add/softplus/mul
   consumers, F32 `ssm_dt`/`ssm_a` vectors, output layouts, and fixed in-order
   queue before submission.
3. Attach persistent per-layer packs to a model-lifetime registry. QKV/z use
   DPAS-v2 packs; alpha/beta/dt/a remain exact native F32.
4. Submit at the earliest matched projection node and mark the other three
   projections plus alpha add/softplus/mul as skipped only after launch returns
   `Q27_XE2_OK`. `SUBMIT_STATE_UNKNOWN` must never run a fallback.
5. Route outputs to qkv, z, the downstream gate tensor, and raw beta. Do not
   simultaneously enable the existing raw-alpha/raw-beta GDN matcher for that
   layer; it expects raw alpha, while this plan already produces the gate.
6. Keep the environment gate default-off and model-specific. Decline for TP,
   LoRA, M other than 6, graph-address changes, insufficient pack headroom, or
   any observable intermediate tensor.

Runtime promotion gates:

- capture a real internal GDN M=6 input and preserve fixed token IDs and DFlash
  acceptance exactly;
- demonstrate at least 2 ms measured cycle saving or 3% same-build cold-suite
  improvement after graph effects, not merely the projected microbenchmark;
- confirm all 48 packs coexist with target, F16 draft KV, DFlash weights, Q6
  top-1 pack, and runtime scratch;
- pass strict cold, cached-zero, fallback, graph-address, and rejection tests.

Protected llama.cpp was not modified during this experiment.
