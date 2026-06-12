# Qwen3.6 Hotrep Route-Plan Grouped-GEMM Screen

Dry run: `False`
Inputs: `data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json, data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json`

## Timing Aggregate

| mode | cases | timed cases | total mean us | p95 us | min us | max us |
|---|---:|---:|---:|---:|---:|---:|
| `exact_full` | 10 | 10 | 189.694 | 217.348 | 180.783 | 239.983 |
| `hotrep_one_launch_rankmax` | 10 | 10 | 197.037 | 218.228 | 180.388 | 222.019 |
| `hotrep_two_launch_rankmax` | 10 | 10 | 389.275 | 421.110 | 369.626 | 430.058 |

## Shape Aggregate

| mode | stage | cases | rows mean/max | experts mean/max | active experts mean/max | max alloc MiB |
|---|---|---:|---:|---:|---:|---:|
| `exact_full` | `gemm1` | 10 | 128.0/128 | 256.0/256 | 43.4/58 | 128.56 |
| `exact_full` | `gemm2` | 10 | 128.0/128 | 256.0/256 | 43.4/58 | 66.52 |
| `hotrep_one_launch_rankmax` | `gemm1` | 10 | 32.0/32 | 68.1/70 | 21.9/25 | 35.15 |
| `hotrep_one_launch_rankmax` | `gemm2` | 10 | 32.0/32 | 68.1/70 | 21.9/25 | 18.18 |
| `hotrep_two_launch_rankmax` | `gemm1` | 10 | 32.0/32 | 68.1/70 | 21.9/25 | 35.15 |
| `hotrep_two_launch_rankmax` | `gemm2` | 10 | 32.0/32 | 68.1/70 | 21.9/25 | 18.18 |

## Interpretation

- `hotrep_one_launch_rankmax` is the ideal one-dispatch shape lower-bound for a per-rank hot+cold table.
- `hotrep_two_launch_rankmax` estimates the launch-tax version. If it loses while one-launch wins, the implementation needs a real fused/persistent path.

## Timing Command

```bash
python3 scripts/bench-qwen36-hotrep-route-plan-gemm.py \
  --route-plan-json data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json \
  --output-json data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing.json \
  --markdown-out data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing.md
```
