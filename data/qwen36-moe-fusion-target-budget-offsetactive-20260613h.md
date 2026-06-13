# Qwen3.6 MoE Fusion Target Budget

## Endpoint Budget

- Current decode: `10.048 ms/token`.
- Current corrected speed: `99.533 tok/s`.
- Model-forward timing: `5.461 ms/token`.
- Outside-forward timing estimate: `4.587 ms/token`.
- Target for `200 tok/s`: `5.000 ms/token`.
- Required model-forward saving if outside cost is unchanged: `5.048 ms/token`.
- Required saving across `40` MoE layers: `126.191 us/layer`.

## Primary Route-Replay Layer Budget

- Primary rows: `1` request row, topk `8` routed rows.
- Route replay samples: `16`.
- Exact current `xpu_fused_moe`: `315.292 us/layer`.
- Exact preallocated staged path: `211.869 us/layer`.
- Exact fused-prologue offset-GEMM path: `209.052 us/layer`.
- Exact fused-prologue active-offset-GEMM path: `211.170 us/layer`.
- Candidate layerlet target for >200 tok/s: `189.101 us/layer`.
- Remaining gap after preallocated staged path: `22.768 us/layer`.
- Remaining gap after offset-GEMM path: `19.952 us/layer`.
- Remaining gap after active-offset-GEMM path: `22.069 us/layer`.

## Grouped-GEMM Floor

- Floor source target rows: `8`.
- `gemm1`: `100.506 us`, `0.086 TOPS`.
- `gemm2`: `93.032 us`, `0.045 TOPS`.
- Two independent GEMM floor: `193.538 us`.
- One-dispatch floor proxy: `100.506 us`.

## Decode Scenarios

| scenario | layer us | saved ms/token | est decode ms | est tok/s |
|---|---:|---:|---:|---:|
| `current_route_replay` | 315.292 | 0.000 | 10.048 | 99.526 |
| `preallocated_staged_lower_bound` | 211.869 | 4.137 | 5.911 | 169.184 |
| `fused_prologue_staged_lower_bound` | 286.142 | 1.166 | 8.882 | 112.591 |
| `fused_prologue_offset_gemm_lower_bound` | 209.052 | 4.250 | 5.798 | 172.471 |
| `fused_prologue_active_offset_gemm_lower_bound` | 211.170 | 4.165 | 5.883 | 169.988 |
| `two_independent_grouped_gemm_floor` | 193.538 | 4.870 | 5.178 | 193.143 |
| `one_dispatch_floor_proxy` | 100.506 | 8.591 | 1.456 | 686.714 |
| `required_for_target` | 189.101 | 5.048 | 5.000 | 200.000 |

## Decision

- The next fused/persistent MoE layerlet must target roughly `189.101 us` or better for rows=`1` while matching `xpu_fused_moe` numerically.
- Two separate small-M grouped GEMM dispatches already exceed that budget.
- A viable non-speculative kernel needs one resident/fused dispatch boundary for route/remap, quant, GEMM1, activation, quant2, GEMM2, and gather, or a comparable way to amortize the fixed dispatch floor.
- If that cannot be shown in one-layer replay, the next >200 tok/s path should shift to exact target-verified speculation.
