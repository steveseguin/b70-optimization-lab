# Qwen3.6 Hotrep Route-Plan Grouped-GEMM Screen

Dry run: `True`
Inputs: `data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json, data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json`

## Timing Aggregate

| mode | cases | timed cases | total mean us | p95 us | min us | max us |
|---|---:|---:|---:|---:|---:|---:|
| `exact_full` | 10 | 0 | nan | nan | nan | nan |
| `hotrep_one_launch_rankmax` | 10 | 0 | nan | nan | nan | nan |
| `hotrep_two_launch_rankmax` | 10 | 0 | nan | nan | nan | nan |

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

- This artifact validates shape extraction only. Run without `--dry-run` in a clean XPU benchmark window to get timings.
- The shape aggregate compares the current full expert table with the hot-replicated per-rank lower-bound shapes before any endpoint or kernel change.

## Timing Command

```bash
python3 scripts/bench-qwen36-hotrep-route-plan-gemm.py \
  --route-plan-json data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json \
  --output-json data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing.json \
  --markdown-out data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing.md
```
