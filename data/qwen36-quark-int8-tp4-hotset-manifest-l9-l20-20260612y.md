# Qwen3.6 MoE Hotset Manifest

Window size: `16`

## Layer Summary

| layer | sources | rec | top32 mean | top32 min | top64 mean | top64 min | top32 union | top32 intersection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `language_model.model.layers.9.mlp.experts` | 6 | 64 | 0.784 | 0.520 | 0.887 | 0.750 | 69 | 0 |
| `language_model.model.layers.20.mlp.experts` | 6 | 64 | 0.802 | 0.569 | 0.910 | 0.784 | 62 | 2 |

## Recommended Replay Windows

### Layer 9

- Recommended hotset: top-64 with `64` experts.
- Expert IDs: `95,2,191,164,36,161,255,170,18,59,243,38,61,44,197,47,207,250,166,81,106,189,21,41,73,198,171,54,227,245,29,251,116,188,70,156,248,94,200,120,186,140,141,108,203,20,126,12,209,246,155,254,180,123,53,239,8,136,213,218,210,14,183,31`
- `route6_exact` starts: `0,1,2,46,78` (topk ids: `True`).
  - `grouped_gemm_dry_run`: `python3 scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py --dry-run --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl --route-layer-regex 'layers[.]9[.]' --route-start-indices 0,1,2,46,78 --route-window-size 16`
  - `fused_moe_rows_1_16`: `/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl --route-layer-regex 'layers[.]9[.]' --rows 1,16 --route-start-indices 0,1,2,46,78`
- `pc_math` starts: `5,22,52,58,85,211` (topk ids: `False`).
  - `grouped_gemm_dry_run`: `python3 scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py --dry-run --route-jsonl data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-math-reasoning.jsonl --route-layer-regex 'layers[.]9[.]' --route-start-indices 5,22,52,58,85,211 --route-window-size 16`
- `pc_repetitive` starts: `7,31,94,157,176,220` (topk ids: `False`).
  - `grouped_gemm_dry_run`: `python3 scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py --dry-run --route-jsonl data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-repetitive.jsonl --route-layer-regex 'layers[.]9[.]' --route-start-indices 7,31,94,157,176,220 --route-window-size 16`

### Layer 20

- Recommended hotset: top-64 with `64` experts.
- Expert IDs: `191,186,99,116,239,224,185,113,83,151,52,117,41,115,7,206,237,110,107,53,171,80,127,121,205,135,3,159,179,72,175,242,56,194,42,216,155,11,157,126,207,136,137,203,49,180,143,235,247,193,141,36,232,71,10,238,234,198,33,35,89,108,47,184`
- `route5_exact` starts: `11,12,13,52,63` (topk ids: `True`).
  - `grouped_gemm_dry_run`: `python3 scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py --dry-run --route-jsonl data/qwen36-quark-int8-tp4-routecapture5-routes-rank0-20260611.jsonl --route-layer-regex 'layers[.]20[.]' --route-start-indices 11,12,13,52,63 --route-window-size 16`
  - `fused_moe_rows_1_16`: `/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py --route-jsonl data/qwen36-quark-int8-tp4-routecapture5-routes-rank0-20260611.jsonl --route-layer-regex 'layers[.]20[.]' --rows 1,16 --route-start-indices 11,12,13,52,63`
- `pc_math` starts: `15,39,102,165,172,228` (topk ids: `False`).
  - `grouped_gemm_dry_run`: `python3 scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py --dry-run --route-jsonl data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-math-reasoning.jsonl --route-layer-regex 'layers[.]20[.]' --route-start-indices 15,39,102,165,172,228 --route-window-size 16`
- `pc_repetitive` starts: `6,33,96,101,159,222` (topk ids: `False`).
  - `grouped_gemm_dry_run`: `python3 scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py --dry-run --route-jsonl data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-repetitive.jsonl --route-layer-regex 'layers[.]20[.]' --route-start-indices 6,33,96,101,159,222 --route-window-size 16`

## Promotion Rules

- Hotset fast paths must preserve exact Quark W8A8 math with cold-expert fallback.
- A route replay win is not enough; live promotion must reduce the accepted model-forward sync bucket.
- Keep exact canaries and provenance guard before any endpoint speed claim.
