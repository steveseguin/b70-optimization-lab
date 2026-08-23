# Ornith 1.5 35B-A3B: full-attention gate CONT bypass is serving-negative

Date: 2026-08-23 EDT

Status: **CLOSED PERFORMANCE NEGATIVE — do not ship**

Ornith retains Qwen's ten full-attention gate chains. In one-token decode each
chain presents a strided `[256,16]` gate view, materializes a contiguous
4,096-element copy, applies sigmoid, and multiplies the attention output. The
generic SYCL backend already fuses sigmoid and multiply, leaving the `CONT`
copy as the only removable launch. This default-off candidate read the original
strided view directly in the existing sigmoid-times-attention operation.

The strict graph matcher fired 1,270 times in the forced 128-token run and
61,320 times in each fresh candidate server suite. The control and candidate
both produced the canonical extracted transcript SHA-256
`2e7965fcdc273f0433df359cff5188ae3585426fd32f28536121d1b5e35dad18`.

The mirrored same-binary engine screen was slightly positive:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `133.663784`, `133.254532` | **133.459158** |
| gate CONT bypass | `133.930232`, `133.666972` | **133.798602** |

That directly measured engine delta is **+0.254%**. Because the signal was
small, it proceeded to the required fresh-serving screen rather than being
promoted from a microbenchmark.

The fresh-server A/B/B/A result rejected it:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `133.443240`, `132.347884` | **132.895562** |
| gate CONT bypass | `132.625210`, `132.466651` | **132.545931** |

That directly measured serving delta is **-0.263%**. All four arms used a
fresh server and the same fixed 12-prompt suite; every prompt ran once,
`cached_tokens` was zero for every response, and every final gate passed. The
candidate therefore does not enter the accepted 11-feature stack. This also
demonstrates why Qwen-derived structural candidates must be validated on
Ornith rather than assumed to transfer as performance wins.

The complete incremental source is preserved at
`../patches/llamacpp-ornith15-attn-gate-server-performance-negative-20260823.patch`.
Raw exactness, engine, and server records are under
`../data/ornith-attn-gate-*`; the structured decision is
`../data/2026-08-23-ornith35b-attn-gate-summary.json`.
