# Qwen3.6 MoE Hot-Set Plan

Captured layers: `3`
TP size: `4`
Per local-shard expert bytes: `795648`

## Memory Estimate

| hot set | captured local-rank MiB | all 40 layers local-rank MiB |
|---:|---:|---:|
| 16 | 36.4 | 485.6 |
| 32 | 72.8 | 971.2 |
| 64 | 145.7 | 1942.5 |

## Layer Coverage

| layer | active experts | p50 window active | top16 | top32 | top64 | top32 MiB/rank |
|---|---:|---:|---:|---:|---:|---:|
| `language_model.model.layers.9.mlp.experts` | 111 | 47.0 | 0.511 | 0.722 | 0.916 | 24.3 |
| `language_model.model.layers.14.mlp.experts` | 126 | 50.0 | 0.421 | 0.645 | 0.874 | 24.3 |
| `language_model.model.layers.21.mlp.experts` | 119 | 48.5 | 0.489 | 0.683 | 0.864 | 24.3 |

## Interpretation

- Top-32 hot-set repack is small enough to test per layer before considering a full all-layer cache.
- Top-64 captures much more traffic but roughly doubles the local-rank cache footprint.
- Use this as a planning estimate only; endpoint promotion still requires exact sentinel parity and speed proof.
