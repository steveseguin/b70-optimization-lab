# MiniMax MoE Up-Kernel Tile Sweep Negative

Date: 2026-05-20

## Context

The promoted MiniMax M2.7 AutoRound path remains `89.314195` output tok/s and `119.085594` total tok/s at p512/n1536, ctx2048, batch 1, TP4 on 4x Intel Arc Pro B70.

A default-off llm-scaler MoE kernel trace was added with `LLM_SCALER_MOE_TRACE_KERNELS=1`. On a small p64/n4 diagnostic, the traced MiniMax decode path showed the routed up projection as the bigger MoE kernel target:

- `moe ws up routed cutlass int4`: 992 calls, `179.813 ms` total, `0.181263 ms` average, p50 `0.044480 ms`, p95 `0.542222 ms`, max `8.245593 ms`.
- `moe ws down cutlass int4`: 992 calls, `27.298 ms` total, `0.027518 ms` average, p50 `0.025280 ms`, p95 `0.042750 ms`, max `0.109271 ms`.

That made the work-sharing up-kernel `N_TILE` choice a reasonable default-off tuning target. The active default remains unchanged unless `VLLM_XPU_MOE_WS_UP_NTILE` is set.

## Results

All tile variants below passed the raw145 n64 exact token hash `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`, so these are performance rejections, not quality failures.

| Variant | p512/n1536 elapsed | Output tok/s | Total tok/s | Decision |
| --- | ---: | ---: | ---: | --- |
| promoted default | n/a | `89.314195` | `119.085594` | keep |
| `VLLM_XPU_MOE_WS_UP_NTILE=1` | `17.510644 s` | `87.718075` | `116.957434` | reject |
| `VLLM_XPU_MOE_WS_UP_NTILE=3` | `17.390517 s` | `88.323997` | `117.765330` | reject |
| `VLLM_XPU_MOE_WS_UP_NTILE=6` | `19.004272 s` | `80.823931` | `107.765241` | reject |

`N_TILE=1` also had an unusually expensive first compile/profile pass: about `154 s` torch.compile time in the raw smoke and a cold n64 decode estimate around `11.4` output tok/s. The warmed p512/n1536 run recovered normal cache loading but remained below the promoted default.

## Decision

No LocalMaxxing submission. These are not promoted results.

The evidence says simple accumulator tile-size tuning is exhausted for the current up kernel. Larger tiles reduce repeated activation loads but increase register pressure; smaller tiles reduce pressure but multiply the number of column-tile work items and activation reloads. The next MoE path should be a deeper kernel/layout change, not another forced `N_TILE` value.

## Next Work

- Keep `VLLM_XPU_MOE_WS_UP_NTILE` unset for promoted MiniMax runs.
- Keep `LLM_SCALER_MOE_TRACE_KERNELS=1` as a diagnostic-only synchronous trace flag.
- If returning to the MoE up kernel, investigate data/layout changes that reduce repeated `x` loads without increasing accumulator pressure, or fuse adjacent router/top-k/up work in a way that removes a framework boundary.
- Continue to require raw145 n64/n256, semantic, arithmetic repeat, and extended sixpack before promoting any speed result.
