# ReplaySSM sibling-V-head workgroup sharing: no win

## Hypothesis

The promoted TP2/FP16 ReplaySSM decode launches one workgroup for each
`(row, k_head, v_head)`, even though each K head feeds three V heads. A
specialized kernel could launch one workgroup per `(row, k_head, v_bucket)`,
share normalized Q/K, Gram matrices, and historical K scores, then process the
three sibling V heads serially.

## Prototype

The default-off operation
`gdn_replayssm_tp2_fp16_sibling_vhead_decode` specialized the exact record
shape: one row, spec length four, cache length eight, FP16 state, 8 local K
heads, 24 local V heads, and 128-wide K/V dimensions. It reduced the launch
from 96 workgroups to 32 without adding global intermediate buffers. The
legacy operation remained unchanged and provided the same-process control.

The isolated source snapshot is:

`patches/qwen36-27b-autoround-int4-b70/vllm-xpu-replayssm-sibling-vhead-20260711.patch.gz`

The benchmark gained an explicit `--sibling-vhead` diagnostic mode. This is a
kernel microbenchmark only, not an endpoint or LocalMaxxing result.

## Four-GPU result

Compact result:

`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-sibling-vhead-4gpu-20260711.json`

With 100 warmup and 2,000 measured iterations per card, all four cards were
nearly identical:

| GPU | legacy decode | sibling-V-head | regression | exact output/state |
| --- | ---: | ---: | ---: | --- |
| 0 | 30.511 us | 62.623 us | +105.25% | yes |
| 1 | 30.515 us | 62.142 us | +103.64% | yes |
| 2 | 30.524 us | 62.345 us | +104.25% | yes |
| 3 | 30.516 us | 62.609 us | +105.17% | yes |

The candidate was bit-exact for output, checkpoint, `d_cache`, `k_cache`,
`g_cache`, pending state, and pending length. The loss is architectural rather
than variance: serially processing three sibling V heads removes too much
parallelism, while the shared Q/K work is too small to compensate.

## Decision

Closed without an endpoint run. The prototype was preserved, removed from the
active source tree, and the production extension restored. Do not repeat the
one-workgroup-per-K-head design on this shape. A future sharing design must
retain V-head concurrency, for example through cooperative sibling subgroups,
and should first demonstrate that occupancy and register pressure remain at
least as good as the 96-workgroup control.
