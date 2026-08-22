# LFM2.5 2.6B — neural.download packet (DRAFT: benchmarks pending)

Status: **intake verified (direct+ordinary I/O) and baseline PASSED**
(2026-08-22). Lane: novice single-card.

**Intake diagnostic baseline (1x B70, 8K ctx, f16 KV, target-only,
128/100 window, cache-zero verified): `133.328 tok/s` median /
`132.988` p10.** Full packet operating points still pending.

## Identity

| Field | Value |
| --- | --- |
| Model | LFM2.5 2.6B, arch `lfm2` (hybrid conv/attention, 30 blocks, embed 2048, native ctx 131072) |
| File | `LFM2.5-2.6B-Q8_0.gguf` |
| SHA-256 | `1e22128dfa128bdfb684da167e74e072d0a056baa7d06d9f280291e2839b0fc9` |
| Source | `LiquidAI/LFM2.5-2.6B-GGUF` @ `f4a289c8a200a5ca71005ba7abc2dad33058a450` |
| Store | `/mnt/usb-models/llm-models/lfm2.5-2.6b-q8/` (catalog id `lfm25-26b-q8`) |
| Base | upstream llama.cpp `9fee29e9435f865ec0b811a783a6471a136d9317`, SYCL AOT bmg-g31, IntelLLVM 2026.0.0 |
| Device | 1x Intel Arc Pro B70 (32 GiB) |

Question this packet answers: smallest honest single-command B70 recipe.

## Recipe, benchmarks, quality — TBD (per the packet standard)
