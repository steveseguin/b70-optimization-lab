# Qwen3.6 Hot-Replicated Route Work Queue Plan

Input: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`
Layer filter: `layers[.]9[.]`
Hotset size: `64`
Ranks: `4`

## Summary

- Windows: `5`; assignments/window mean `128.0`.
- Hot coverage mean/p95/min: `0.870` / `0.938` / `0.750`.
- Cold rows mean/max: `16.6` / `32.0`.
- Per-rank max rows mean/p95/max: `32.0` / `32.0` / `32.0`.
- Imbalance max/mean mean/p95/max: `1.000` / `1.000` / `1.000`.

## Windows

| start | hot coverage | hot rows | cold rows | rows by rank | imbalance |
|---:|---:|---:|---:|---|---:|
| 0 | 0.938 | 120 | 8 | `[32, 32, 32, 32]` | 1.000 |
| 1 | 0.938 | 120 | 8 | `[32, 32, 32, 32]` | 1.000 |
| 2 | 0.938 | 120 | 8 | `[32, 32, 32, 32]` | 1.000 |
| 46 | 0.750 | 96 | 32 | `[32, 32, 32, 32]` | 1.000 |
| 78 | 0.789 | 101 | 27 | `[32, 32, 32, 32]` | 1.000 |

## Decision

- The route metadata can be represented exactly as per-rank hot/cold queues plus a gather map; no expert dropping or approximate routing is required.
- This is still metadata only. A speed claim requires a one-launch kernel path that consumes these queues and proves exact output parity against `xpu_fused_moe` on the same windows.
