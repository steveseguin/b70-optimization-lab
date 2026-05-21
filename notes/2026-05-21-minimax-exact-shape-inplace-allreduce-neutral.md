# MiniMax M2.7 Exact-Shape In-Place Allreduce Screen Neutral

Date: 2026-05-21

## Candidate

Added a default-off exact-shape gate for the existing alias-correct
`all_reduce_inplace` custom op:

```bash
VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_SHAPES='float16:1x3072;float16:2x3072'
```

The goal was to target only the FP16 hidden-state allreduce shapes that showed
up as the largest synchronized decode buckets, without repeating the broader
`numel <= 4096` in-place threshold that was already rejected.

## Validation

- `python -m py_compile` passed for both source and installed
  `vllm/distributed/parallel_state.py`.
- `bash -n` passed for the strict MiniMax quality harness after adding env
  capture for `VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_SHAPES`.
- The gate defaults off, so the promoted path is unchanged unless the env is
  explicitly set.

## Performance Screen

All screens used 4x B70, TP4, MiniMax M2.7 AutoRound INT4, p512/n1536,
ctx2048, MBT512, block256, PIECEWISE graph, one warmup, and four measured
warm in-process repeats.

| Run | Env delta | Mean output tok/s | Mean total tok/s | Stdev output tok/s |
| --- | --- | ---: | ---: | ---: |
| Paired control | env unset | `92.425711` | `123.234282` | `0.038593` |
| Exact `(2,3072)` only | `float16:2x3072` | `92.379302` | `123.172402` | `0.029758` |
| Exact `(1,3072)` plus `(2,3072)` | `float16:1x3072;float16:2x3072` | `92.446882` | `123.262510` | `0.030445` |

The two-shape candidate was only `+0.021171` output tok/s over paired control,
or about `+0.023%`. That is inside normal run noise and not enough to justify
a full strict quality run.

## Decision

Neutral. Do not promote and do not submit to LocalMaxxing.

The code is useful as a default-off diagnostic/screening knob because it lets
future runs isolate exact allreduce shapes without retesting a broad threshold,
but this specific `(1,3072)/(2,3072)` decode route is not a real speed win.

## Artifacts

- `(2,3072)` screen JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/inplace-shape-2x3072-screen-20260521T083822Z/minimax-inplace-shape-2x3072-screen-p512n1536.json`
- `(1,3072);(2,3072)` screen JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/inplace-shapes-1x2x3072-screen-20260521T084603Z/minimax-inplace-shapes-1x2x3072-screen-p512n1536.json`
- Paired control JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/default-after-shape-gate-control-20260521T085327Z/minimax-default-after-shape-gate-control-p512n1536.json`
- Data summary:
  `data/minimax-m27-exact-shape-inplace-allreduce-neutral-20260521.json`
- Patch:
  `patches/minimax-exact-shape-inplace-allreduce-neutral-20260521.patch`
