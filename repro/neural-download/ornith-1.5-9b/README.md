# Ornith 1.5 9B — neural.download packet (DRAFT: benchmarks pending)

Status: **intake verified (direct+ordinary I/O) and baseline PASSED**
(2026-08-22). Lane: beginner-plus single-card.

**Intake diagnostic baseline (1x B70, 8K ctx, f16 KV, target-only,
128/100 window, cache-zero verified): `50.109 tok/s` median /
`50.061` p10.** Full packet operating points still pending.

## Identity

| Field | Value |
| --- | --- |
| Model | Ornith 1.5 9B (dense), arch `qwen35`, 32 layers, embed 4096, native ctx 262144 |
| File | `Ornith-1.5-9B-Q8_0.gguf` |
| SHA-256 | `6874eeb25c71081dc8f0bbe88f3ebb786312447132745371cd980bce95d259b9` |
| Source | `ornith-ai/Ornith-1.5-9B-GGUF` @ `85bf2b98cdcbad4291cb4f46943526cc089f75a0` |
| Store | `/mnt/usb-models/llm-models/ornith-1.5-9b-q8/` (catalog id `ornith-15-9b-q8`) |
| Base | upstream llama.cpp `9fee29e9435f865ec0b811a783a6471a136d9317`, SYCL AOT bmg-g31, IntelLLVM 2026.0.0 |
| Device | 1x Intel Arc Pro B70 (32 GiB) |

Question this packet answers: recent official one-card model as a beginner
package candidate.

## Recipe, benchmarks, quality — TBD

Filled only from measured runs per
[the packet standard](../../../docs/neural-download-packet-standard.md):
intake `verify` (direct+ordinary) -> `run-model-intake-baseline.sh`
(1 B70, f16 KV, 8K, target-only) + diagnostic bench gate -> packet
operating points (2 fresh-server runs each) -> canary battery.

## Context-depth sweep (llama-bench raw engine rates, fa on, 5 reps)

![depth sweep](depth-sweep.svg)

| Depth | decode tg128 tok/s (±σ) | prefill pp2048 tok/s (±σ) |
|---:|---:|---:|
| 0 | 50.29 (±0.00) | 3184.5 (±10.0) |
| 2,048 | 49.34 (±0.01) | 1623.0 (±3.2) |
| 4,096 | 48.55 (±0.01) | 1601.2 (±2.4) |
| 8,192 | 47.04 (±0.01) | 1568.6 (±2.1) |
| 16,384 | 44.35 (±0.01) | 1489.2 (±2.8) |
| 24,576 | 41.96 (±0.00) | 1448.8 (±20.3) |
| 32,768 | 39.84 (±0.01) | 1313.7 (±3.4) |

Raw engine rates run above server-suite medians by design (no HTTP/sampling); use the suite median as the serving expectation and this curve for the depth trend. Evidence: `ornith-15-9b-q8.sweep.json` + `ornith-15-9b-q8.meta.json` (model/bench shas inside).
