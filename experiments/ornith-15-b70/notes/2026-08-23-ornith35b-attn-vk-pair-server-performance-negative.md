# Ornith 1.5 35B-A3B: paired full-attention V/K DMMV is serving-negative

Date: 2026-08-23 EDT

Status: **CLOSED PERFORMANCE NEGATIVE — do not ship**

Ornith 1.5 retains enough of its Qwen-family full-attention structure for a
Qwen-style launch-fusion experiment to be well motivated. In each of its ten
full-attention layers, the V and K projections consume the same 2048-element
FP32 activation and produce separate live 512-element outputs. Both already
use the reordered ESIMD DMMV path. This default-off candidate placed those two
unchanged row-pair dot products in one larger work-group grid, removing ten
kernel submissions per decoded token without changing the arithmetic used for
either projection.

The strict shape/name/graph matcher fired 1,270 times in the 128-token
correctness run and 61,320 times in every 12-prompt server candidate. Its
poison mode aborted at the intended matcher. The candidate retained the
canonical transcript SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.

The mirrored same-binary engine screen was consistently but only slightly
positive:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `132.712193`, `132.810833` | **132.761513** |
| paired attention V/K | `132.922421`, `133.014196` | **132.968309** |

That directly measured engine delta is **+0.156%**. Because the signal was
small, it proceeded to the required fresh-serving screen rather than being
promoted from the engine microbenchmark.

The fresh-server A/B/B/A result rejected it:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `129.771032`, `130.578969` | **130.175001** |
| paired attention V/K | `130.704541`, `129.268632` | **129.986587** |

That directly measured serving delta is **-0.145%**. All four arms used a
fresh server and the same fixed 12-prompt suite; every prompt ran once,
`cached_tokens` was zero for every response, and every final gate passed. The
candidate spread also straddles the controls, so the launch reduction is not a
stable serving improvement. It is not part of the accepted 11-feature stack.

The complete incremental candidate source is preserved at
`../patches/llamacpp-ornith15-attn-vk-pair-server-performance-negative-20260823.patch`.
Raw exactness, engine, server, and freshness records are under
`../data/ornith-qk-attn-vk-*`; the structured decision is
`../data/2026-08-23-ornith35b-attn-vk-pair-summary.json`.
