# Qwen3.6 MoE Fusion Target Budget

## Endpoint Budget

- Current decode: `10.039 ms/token`.
- Current corrected speed: `99.618 tok/s`.
- Model-forward timing: `8.438 ms/token`.
- Outside-forward timing estimate: `1.600 ms/token`.
- Target for `200 tok/s`: `5.000 ms/token`.
- Required model-forward saving if outside cost is unchanged: `5.039 ms/token`.
- Required saving across `40` MoE layers: `125.973 us/layer`.

## Primary Route-Replay Layer Budget

- Primary rows: `1` request row, topk `8` routed rows.
- Route replay samples: `32`.
- Exact current `xpu_fused_moe`: `294.145 us/layer`.
- Exact preallocated staged path: `220.530 us/layer`.
- Candidate layerlet target for >200 tok/s: `168.173 us/layer`.
- Remaining gap after preallocated staged path: `52.358 us/layer`.

## Grouped-GEMM Floor

- Floor source target rows: `8`.
- `gemm1`: `100.506 us`, `0.086 TOPS`.
- `gemm2`: `93.032 us`, `0.045 TOPS`.
- Two independent GEMM floor: `193.538 us`.
- One-dispatch floor proxy: `100.506 us`.

## Decode Scenarios

| scenario | layer us | saved ms/token | est decode ms | est tok/s |
|---|---:|---:|---:|---:|
| `current_route_replay` | 294.145 | 0.000 | 10.039 | 99.612 |
| `preallocated_staged_lower_bound` | 220.530 | 2.945 | 7.094 | 140.958 |
| `two_independent_grouped_gemm_floor` | 193.538 | 4.024 | 6.015 | 166.261 |
| `one_dispatch_floor_proxy` | 100.506 | 7.746 | 2.293 | 436.047 |
| `required_for_target` | 168.173 | 5.039 | 5.000 | 200.000 |

## Decision

- The next fused/persistent MoE layerlet must target roughly `168.173 us` or better for rows=`1` while matching `xpu_fused_moe` numerically.
- Two separate small-M grouped GEMM dispatches already exceed that budget.
- A viable non-speculative kernel needs one resident/fused dispatch boundary for route/remap, quant, GEMM1, activation, quant2, GEMM2, and gather, or a comparable way to amortize the fixed dispatch floor.
- If that cannot be shown in one-layer replay, the next >200 tok/s path should shift to exact target-verified speculation.
