# Qwen27 Token-Tree Retest On Current ReplaySSM/Draft-INT4 Recipe: No Win

Date: 2026-07-06

Classification: strict fresh diagnostic screen, quality disabled, no promote,
no LocalMaxxing.

## Purpose

The earlier token-tree mechanical screen used the older BF16-scale INT8
LM-head recipe. The current valid record uses ReplaySSM exact GDN state
handling plus runtime INT4 draft LM-head BF16 scales, so the draft side is
cheaper. This retest asked whether the same token-tree shapes become useful on
the current recipe.

This was a same-window four-GPU screen with `RUN_QUALITY=0`. Every completed
row still used the fixed realistic Qwen suite, one cold response per prompt,
`cached_tokens=0`, token-id timing, and no prompt/KV/history reuse. Because no
candidate beat control, no repeat64 quality run was needed.

## Common Runtime

- model: `webhie/Qwen3.6-27B-int4-AutoRound`
- TP1, one B70 per candidate, four candidates in parallel
- XPU graph on, `max_cudagraph_capture_size=8`
- ReplaySSM exact GDN path:
  `VLLM_XPU_GDN_REPLAYSSM_SPEC=1`,
  `VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1`,
  `VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1`
- target LM-head: runtime INT8 with BF16 scales
- draft LM-head: runtime INT4, group size 128, BF16 scales
- suite: `repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`

## Results

| Label | Tree / MTP shape | Median tok/s | p10 | Mean | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| `qwen27-treecurrent-control-20260706T0700tree` | ordinary MTP3/cg8 | `67.79670763509579` | `61.79906487277237` | `67.57287578649758` | pass |
| `qwen27-treecurrent-root3-20260706T0700tree` | root top-3 depth-1, `[(0,), (1,), (2,)]` | `67.69083946661863` | `62.00066763556559` | `67.34304762081933` | pass |
| `qwen27-treecurrent-root2-20260706T0700tree` | root top-2 depth-1, `[(0,), (1,)]` | `59.159016305927835` | `54.710596269300886` | `56.39229788944385` | pass |
| `qwen27-treecurrent-binary-depth2-20260706T0700tree` | binary depth-2, six verifier rows | `12.708958388532118` | `10.392335222627393` | `12.711543042689835` | pass |

Tracked compact summaries:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-treecurrent-control-20260706T0700tree-candidate-summary-20260706T0700tree.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-treecurrent-root2-20260706T0700tree-candidate-summary-20260706T0700tree.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-treecurrent-root3-20260706T0700tree-candidate-summary-20260706T0700tree.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-treecurrent-binary-depth2-20260706T0700tree-candidate-summary-20260706T0700tree.json
```

## Decision

No endpoint candidate.

Root-3 is effectively tied with the same-window control and slightly slower in
median and mean. The delta is inside normal run variance and has no quality
validation. Root-2 is clearly slower. Binary-depth-2 is unusably slow because
the wider verifier/tree shape dominates despite the faster draft INT4 LM-head.

Do not repeat config-only `speculative_token_tree` sweeps on the current
ReplaySSM/draft-INT4 recipe. Token-tree or branch work is still conceptually
relevant only if the implementation avoids the current dense draft-logits and
wider-verifier costs, and legally regenerates dependent rows and target-owned
bonus tokens.
