# Qwen3.6 W8A8 Grouped-GEMM Roofline Packet

Input: `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing-20260612ah.json`

## Tooling Boundary

- This is an offline estimate from route-exact grouped-GEMM event timings. It does not include hardware DPAS/XMX counters.
- Counter limitation: unitrace/VTune are not installed; xpu-smi EU and bandwidth metrics require elevated MEI access in this environment.
- `active_lower_bound` assumes only active expert weights are read. `full_table_upper_bound` assumes the full expert table could be touched. Reality should sit between those bounds.

## Aggregate

| mode | stage | component | cases | us mean | TOPS mean | active BW TB/s | full-table BW TB/s | shape mean | experts mean | active experts mean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `exact_full` | `gemm1` | `stage` | 10 | 97.138 | 1.413 | 0.245 | 1.419 | 128.0x2048x256 | 256.0 | 43.4 |
| `exact_full` | `gemm2` | `stage` | 10 | 92.556 | 0.725 | 0.133 | 0.754 | 128.0x128x2048 | 256.0 | 43.4 |
| `hotrep_one_launch_rankmax` | `gemm1` | `rankmax_combined` | 10 | 100.965 | 0.337 | 0.108 | 0.354 | 32.0x2048x256 | 67.0 | 20.3 |
| `hotrep_one_launch_rankmax` | `gemm2` | `rankmax_combined` | 10 | 96.072 | 0.175 | 0.056 | 0.191 | 32.0x128x2048 | 67.2 | 19.4 |
| `hotrep_two_launch_rankmax` | `gemm1` | `cold` | 10 | 102.094 | 0.050 | 0.019 | 0.019 | 4.9x2048x256 | 3.6 | 3.6 |
| `hotrep_two_launch_rankmax` | `gemm1` | `hot` | 10 | 96.438 | 0.296 | 0.087 | 0.350 | 27.1x2048x256 | 64.0 | 15.7 |
| `hotrep_two_launch_rankmax` | `gemm2` | `cold` | 10 | 94.665 | 0.026 | 0.009 | 0.009 | 4.8x128x2048 | 3.2 | 3.2 |
| `hotrep_two_launch_rankmax` | `gemm2` | `hot` | 10 | 96.078 | 0.149 | 0.046 | 0.182 | 27.2x128x2048 | 64.0 | 15.9 |

## Interpretation

- `gemm1` exact_full averages `1.413` effective TOPS at `97.138 us` for mean route-window shape `M=128, K=2048, N=256` with `43.4` active experts.
- `gemm2` exact_full averages `0.725` effective TOPS at `92.556 us` for mean route-window shape `M=128, K=128, N=2048` with `43.4` active experts.
- Effective TOPS are very low for a B70-class INT8 path, which is consistent with small-M/skewed-expert grouped-GEMM underutilization, launch/control overhead, or a non-ideal kernel path.
- This supports persistent/tile-native MoE work over more service flag tuning. A speed candidate needs to raise effective TOPS on these exact route windows or amortize multiple target tokens per forward with an exact verifier.
