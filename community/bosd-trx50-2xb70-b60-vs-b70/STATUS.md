# Arc Pro B60 vs B70 — single-card head-to-head (SYCL + Vulkan)

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `B70-tested` for the B70 column; **B60 column is `community-reported`** (reference lab has no B60) |
| Patch review status | n/a — benchmark result, no source patch |
| Tested in reference lab | no |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no (B60 cannot be verified in the reference lab) |

## Provenance

- Contributor: **bosd** (`github.com/bosd`)
- Source PR or URL: this PR; full data in `bosd/trx50-arc-b70-benchmarks`
- Commits: llama.cpp **SYCL** + **Vulkan** builds (oneAPI 2026.0 / Mesa Anv 26.0.7); exact upstream commit `unknown`
- Right-to-submit statement present: yes — own measurements
- Third-party material and attribution: none

## Claim

A single Arc Pro **B60 (G21, 24 GB)** runs at **~78–88% of a B70's generation speed** and **~68–73% of its prompt-processing**, while drawing **~56–63% of the power** → **1.2–1.6× more tokens/joule**; it also POSTs (G21 GOP) where the B70 (G31) does not.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 1× **Arc Pro B60** (Battlemage G21, `8086:e211`, 24 GB / ~21.5 usable) vs 1× **Arc Pro B70** (G31, `8086:e223`, 32 GB), same host, single card each |
| OS / kernel | Fedora Server 44, kernel **7.0.10** |
| GPU driver (`i915`/`xe`) and version | **`xe`** |
| compute-runtime / level-zero | NEO **26.18.38308.1** (SYCL); Mesa **26.0.7** (Vulkan/Anv) |
| Engine / image and exact version | llama.cpp `llama-bench`, **SYCL** (oneAPI 2026.0) and **Vulkan** (Mesa Anv); commit `unknown` |
| Model repo and revision | Qwen3-4B (Q4), Qwen3.6-35B-A3B (Q4_0) |
| Quantization (weights / KV / activations) | weights Q4 / Q4_0; KV f16; no activation quant |
| Command and environment variables | `llama-bench -p 512 -n 128`; per-backend defaults |
| Prompt / output / context lengths, concurrency | pp512 / tg128; concurrency 1 |
| Cache and speculation policy | cold, defaults; no speculation |
| Metric definition, repeats, dispersion, TTFT | pp512 & tg128 t/s (llama-bench defaults); W = GPU-only (`xe` card energy counter, single card); TTFT n/a |
| Logs / JSON / durable links | https://github.com/bosd/trx50-arc-b70-benchmarks/blob/master/results/b60-vs-b70.md |

## Reference Lab Environment

Nothing executed in the reference lab. **The B60 is not present in the reference lab, so the B60 column is inherently `community-reported`** and cannot be promoted.

## What Was Actually Run Here

Nothing in the reference lab. Both columns measured on the contributor's TRX50 (B60 and B70 in the same host, one card at a time).

## Findings

- **Generation:** B60 ≈ **78–88%** of a B70 (88% on the SYCL production path).
- **Prompt processing:** B60 ≈ **68–73%** — the B70's extra Xe cores show on compute-bound prefill.
- **Power:** B60 draws **~56–63%** of a B70 (60–81 W vs 96–144 W) → **1.2–1.6× tokens/joule**.
- **POST/GOP:** the B60 (G21) produces POST video and can double as a console GPU; the B70 (G31) produces **no** pre-OS video on this platform — a practical B60 advantage for headless-build bring-up.
- **Do not tensor-split B60+B70:** the 24/32 GB mismatch wastes the B70's VRAM and the slower B60 bottlenecks the pair; keep the B60 standalone.

## Known Issues

None found — result-only submission.

## Open Questions For The Contributor

Nothing needed for correctness; the B60 column simply cannot reach `B70-verified` without a B60 in the reference lab. Useful add: the SYCL row for Qwen3.6-35B-A3B on the B60 (only Vulkan captured for that model on B60).

## Disposition

Stays `community/`; the B60 column is `community-reported` by definition (no B60 in the reference lab). Recorded as reference data for anyone weighing B60 vs B70 for an Intel Arc inference build. CONTRIBUTING explicitly welcomes B50/B60/B65 work.
