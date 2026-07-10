# Qwen27 acceptance-gate statistical revision

Date: 2026-07-10

Status: workflow correction; no endpoint throughput result and no
LocalMaxxing submission.

## Correction

Retire `3.3 visible tokens/step` as a fixed endpoint-trial gate. It was a
rounded heuristic from an earlier planning stage, not a statistically derived
threshold. It is sufficient for `100 tok/s` only if the complete verifier step
cost is at most `33 ms`.

For an exact-prefix draft of depth `k`, the offline metric is:

```text
visible tokens/step = 1 + mean(longest exact accepted draft prefix)
```

The current strict MTP3 trace is `2.746954` visible tokens/step. Combining it
with the current valid `68.236263 tok/s` row gives a planning estimate of
`40.2565 ms/step`; this is not a directly paired latency measurement. At that
cost, `100 tok/s` requires `4.02565` visible tokens/step. Historical MTP5 cost
was about `51 ms/step`, requiring about `5.1` visible tokens/step.

## Retrospective paired audit

The stored prompt/sample pairs show:

| Candidate comparison | Delta visible tokens/step | Assessment |
|---|---:|---|
| all position FCs vs shared FC | `+0.393921` | credible within v6b; paired 95% CI `[+0.34557,+0.43565]` |
| rank-256 adapter vs all-FC | `+0.036865` | credible but small; paired 95% CI `[+0.01939,+0.05417]` |
| rank-512 continuation | `+0.011475` | no unseen paired rerun; inconclusive |
| gated stacked refinement | `+0.023945` | only 16 ordered-tail samples; inconclusive |
| direct stacked refinement | at most `-0.351` | clear regression |

Calibrating the rank-256 result to the strict lane projects about `3.29234`
visible tokens/step, or only `81.8 tok/s` at `40.2565 ms/step` before adding
adapter/deeper-MTP runtime cost. The fixed gate did not hide a plausible
standalone `100 tok/s` candidate.

## Replacement rule

For each candidate/control pair:

1. retain per-prompt and per-start exact accepted-prefix values;
2. use a prompt/family-clustered paired bootstrap and correct multi-candidate
   screens with Holm; require one-sided `95% LCB(delta acceptance) > 0`;
3. measure candidate-specific full step cost under the exact depth, graph,
   ReplaySSM, LM-head, model, and runtime identity;
4. compute the conservative ROI bound
   `R_L = 1000 * acceptance_LCB / step_cost_UCB`;
5. require `R_L >= 100 tok/s` for a standalone 100-tok/s mechanism, or record
   an explicit additive contribution when combining independent mechanisms;
6. final endpoint validation uses four-GPU ABBA/BAAB crossover blocks, the 12
   fixed cold prompts, `cached_tokens=0`, hierarchical paired throughput
   analysis, and repeat64 baseline-quality match.

A small component candidate can still receive a bounded endpoint screen when
its paired lower bound exceeds practical measurement noise and its integration
cost is low. It must not be discarded solely for missing `3.3`, and it must
not be promoted solely for beating an offline mean.
