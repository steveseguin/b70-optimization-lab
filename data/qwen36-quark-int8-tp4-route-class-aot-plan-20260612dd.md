# Qwen3.6 Route-Class AOT Plan

- Status: `needs_more_route_windows_before_aot_commit`.
- Records used: `120` / `120`.
- Fixture events: `3`.
- Layers: `40`.
- Global unique route classes: `80`.
- Per-layer exact route classes: `80` (mean `2.000` per layer).
- Exact unique hot-pack memory for seen layers: `408.229 MiB` per TP shard.
- Exact hot-pack fraction of full seen-layer MoE shards: `0.053`.

## Budget Coverage

| classes/layer | mean coverage | min coverage | unique hot-pack MiB | duplicate route-pack MiB |
|---:|---:|---:|---:|---:|
| 1 | 0.667 | 0.667 | 242.812 | 242.812 |
| 2 | 1.000 | 1.000 | 408.229 | 485.625 |
| 3 | 1.000 | 1.000 | 408.229 | 485.625 |
| 4 | 1.000 | 1.000 | 408.229 | 485.625 |
| 8 | 1.000 | 1.000 | 408.229 | 485.625 |

## Top Global Route Classes

- `87178256ce982b5c` count `2`, coverage `0.017`, topk `[41, 29, 222, 231, 207, 28, 75, 139]`
- `49fdc8f825bc02dc` count `2`, coverage `0.017`, topk `[19, 163, 238, 153, 125, 167, 215, 103]`
- `9ee2cd6fbad89db5` count `2`, coverage `0.017`, topk `[219, 243, 202, 62, 168, 251, 82, 214]`
- `b6d420d47c6344d3` count `2`, coverage `0.017`, topk `[174, 83, 179, 158, 168, 18, 143, 79]`
- `9258e5cc1d29120c` count `2`, coverage `0.017`, topk `[72, 199, 4, 59, 191, 226, 29, 75]`
- `ba883e080a17dbfa` count `2`, coverage `0.017`, topk `[205, 138, 94, 102, 211, 17, 175, 214]`
- `baab09722b3fd366` count `2`, coverage `0.017`, topk `[68, 97, 101, 15, 98, 239, 63, 28]`
- `78ed7ba68d273e1d` count `2`, coverage `0.017`, topk `[119, 163, 216, 45, 145, 90, 204, 20]`

## Layer Snapshot

| layer | records | unique classes | top1 coverage | top2 coverage | top3 coverage |
|---|---:|---:|---:|---:|---:|
| layer_00 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_01 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_02 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_03 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_04 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_05 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_06 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_07 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_08 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_09 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_10 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_11 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_12 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_13 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_14 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_15 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_16 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_17 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_18 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_19 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_20 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_21 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_22 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_23 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_24 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_25 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_26 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_27 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_28 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_29 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_30 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_31 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_32 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_33 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_34 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_35 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_36 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_37 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_38 | 3 | 2 | 0.667 | 1.000 | 1.000 |
| layer_39 | 3 | 2 | 0.667 | 1.000 | 1.000 |

## Interpretation

This is an AOT planning gate only. It estimates route-class coverage and hot-pack memory from captured routes; it does not prove speed or quality. Kernel candidates still need graph-path tensor parity, prologue-inclusive timing, quality gates, and an accepted-lane manifest before endpoint promotion.
