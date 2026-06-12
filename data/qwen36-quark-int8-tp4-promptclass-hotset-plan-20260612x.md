# Qwen3.6 MoE Hot-Set Plan

Captured layers: `5`
TP size: `4`
Per local-shard expert bytes: `795648`

## Memory Estimate

| hot set | captured local-rank MiB | all 40 layers local-rank MiB |
|---:|---:|---:|
| 16 | 60.7 | 485.6 |
| 32 | 121.4 | 971.2 |
| 64 | 242.8 | 1942.5 |

## Layer Coverage

| layer | active experts | p50 window active | top16 | top32 | top64 | top32 MiB/rank |
|---|---:|---:|---:|---:|---:|---:|
| `language_model.model.layers.20.mlp.experts` | 158 | 24.0 | 0.438 | 0.628 | 0.830 | 24.3 |
| `language_model.model.layers.14.mlp.experts` | 155 | 23.0 | 0.423 | 0.616 | 0.809 | 24.3 |
| `language_model.model.layers.9.mlp.experts` | 165 | 22.0 | 0.413 | 0.587 | 0.792 | 24.3 |
| `language_model.model.layers.21.mlp.experts` | 150 | 24.0 | 0.421 | 0.598 | 0.787 | 24.3 |
| `language_model.model.layers.8.mlp.experts` | 163 | 22.0 | 0.401 | 0.578 | 0.786 | 24.3 |

## Interpretation

- Top-32 hot-set repack is small enough to test per layer before considering a full all-layer cache.
- Top-64 captures much more traffic but roughly doubles the local-rank cache footprint.
- Use this as a planning estimate only; endpoint promotion still requires exact sentinel parity and speed proof.
