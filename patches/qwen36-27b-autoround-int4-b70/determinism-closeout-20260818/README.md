# Qwen3.6 27B AutoRound INT4 TP2 — determinism/speed closeout source

Preserves the source state this lane finished at on 2026-08-18, when the lane
was closed and work moved to the Qwen3.8 27B INT4 lane.

This packet records **source identity only**. It does not supersede the
`95.384867741895 tok/s` measured result from
[`../record-20260711/README.md`](../record-20260711/README.md), which remains the
retained LocalMaxxing row.

## Contents

| Artifact | Purpose |
| --- | --- |
| `vllm-determinism-commits.bundle` | the two closeout vLLM commits, with prerequisite `95a76ff89173` |
| `vllm-sampler-final-working.patch` | the complete two-commit change as a flat diff |
| `source-manifest.json` | hashes, commit list, and the measured outcome |
| `SHA256SUMS` | manifest of this directory |

Unlike `record-20260711`, these commits are **already public**: they are
reachable from `research/qwen36-int4-exactness-20260818` on
`https://github.com/steveseguin/vllm.git`. The bundle exists for offline restore
and audit, not because the commits are otherwise unavailable.

The vLLM XPU kernels tree is **unchanged** by this closeout and stays at
`2dd55f380df753a10a88fcd9e96192561066e713`, already published on the fork's
`main`.

## What the change does

Both commits target `_xpu_deterministic_greedy_sample` in
`vllm/v1/sample/sampler.py`, the bounded greedy tie break used whenever
`VLLM_XPU_DETERMINISTIC_GREEDY_MARGIN` is set:

1. `011713d34b` stops upcasting the entire logits tensor to fp32 before the
   top-two reduction; only the two surviving values need the wider type.
2. `44fc8fde09` replaces `topk(k=2)` with two masked `max` reductions. On this
   hardware a 248320-wide `topk` measures ~`0.679 ms` per step against ~`0.111 ms`
   for a max reduction; the pair costs ~`0.089 ms`.

The near-tie branch resolves to `min(first, second)`, so the result cannot
depend on the order the two largest entries are returned in. Verified
bit-identical to the previous implementation over 800 sampled tokens including
forced exact ties and forced near ties, then on hardware across three replicates.

## Restore

```bash
git clone https://github.com/vllm-project/vllm.git ~/src/vllm
git -C ~/src/vllm fetch /path/to/vllm-determinism-commits.bundle
git -C ~/src/vllm checkout --detach 44fc8fde09fc311d3099dab10366b672d9142ea4
```

Or simply fetch the published fork branch, which contains the whole research line.

## Measured outcome

| Metric | all-25 suite | 12-prompt suite |
| --- | ---: | ---: |
| deterministic ceiling (this source) | `94.710` | `89.766` |
| fastest non-reproducing configuration | `96.822` | `94.103` |
| retained July record | not measured | `95.385` |

Nothing in the closing campaign beat the July record on the suite that record
was set on. Full analysis:
[`../../../notes/2026-08-18-qwen36-int4-determinism-speed-tradeoff.md`](../../../notes/2026-08-18-qwen36-int4-determinism-speed-tradeoff.md).
