# MiniMax MoE Up-Kernel Tile Sweep Control Addendum

Date: 2026-05-20

After publishing the initial tile-sweep note, I noticed the quick forced-tile screens used the plain throughput harness while the promoted strict result used `--async-engine`. To keep the comparison honest, I ran an additional no-forced-tile quick-screen control under the same harness used by the tile variants.

## Control Runs

- First isolated control, fresh cache root: `21.843152 s`, `70.319523` output tok/s, `93.759364` total tok/s. Rejected as the known cold-cache artifact: KV cache was only `9,472` tokens.
- Warmed same-cache control: `17.327996 s`, `88.642678` output tok/s, `118.190237` total tok/s. KV cache recovered to `17,664` tokens.

## Same-Harness Comparison

| Variant | Output tok/s | Delta vs warmed default control | Decision |
| --- | ---: | ---: | --- |
| no forced tile, warmed control | `88.642678` | baseline | keep default |
| `VLLM_XPU_MOE_WS_UP_NTILE=1` | `87.718075` | `-0.924602` | reject |
| `VLLM_XPU_MOE_WS_UP_NTILE=3` | `88.323997` | `-0.318680` | reject |
| `VLLM_XPU_MOE_WS_UP_NTILE=6` | `80.823931` | `-7.818747` | reject |

## Decision

The original decision remains unchanged. Forced up-kernel `N_TILE` variants are quality-clean on the raw145 n64 smoke but slower than the default under the same quick-screen harness. No LocalMaxxing submission.
