# 2026-06-27T15:28Z Selected-Weight Flags Identity Mistake

## Goal

Test whether two small Gemma 4 MoE selected-weight materialization flags help
after the Q8 MoE-ID reorder breakthrough:

- `LLAMA_GEMMA4_MOE_SKIP_EARLY_WEIGHTS_EXPAND=1`
- `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM=1`

## Result

These runs completed and passed canaries, but they are **not valid
current-record comparisons** because the launch identity accidentally omitted
`LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`. The promoted UB720 record includes that
flag, so these runs are useful only as a benchmark-identity mistake artifact.

| Run | Canary | Fresh row0 tok/s | Support mean tok/s | `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS` | Interpretation |
| --- | ---: | ---: | ---: | --- | --- |
| `data/gemma4-q8-gpu0-q8reorder-ub720-control-screen-20260627T152815Z/` | 256/256 | 169.459 | 169.415 | `<unset>` | Invalid control for current stack |
| `data/gemma4-q8-gpu1-q8reorder-ub720-skipearly-screen-20260627T152815Z/` | 256/256 | 170.056 | 169.277 | `<unset>` | Invalid candidate comparison |
| `data/gemma4-q8-gpu2-q8reorder-ub720-ssws-screen-20260627T152815Z/` | 256/256 | 168.011 | 168.507 | `<unset>` | Invalid candidate comparison |
| `data/gemma4-q8-gpu3-q8reorder-ub720-ssws-skipearly-screen-20260627T152815Z/` | 256/256 | 166.087 | 167.410 | `<unset>` | Invalid candidate comparison |

All reported `cached_tokens=0`, so the issue is not fresh-response validity;
it is run-identity comparability.

## Follow-Up

Rerun the same four-way screen with the full promoted UB720 identity, including
`LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`, before drawing any conclusion about these
two flags on the current stack.
