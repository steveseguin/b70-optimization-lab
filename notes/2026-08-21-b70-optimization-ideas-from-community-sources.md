# External-source intake audit: no cookbook patch promoted

Date: 2026-08-21. Author: lab.

## Outcome

The source review did **not** identify a public, inspectable patch from the
SergiioB cookbook that improved a lab result. No cookbook recipe or benchmark
is a source of truth for the lab's Qwen lanes, and none should be presented as
the origin of the lab's Qwen performance.

The review initially produced a family-hub catalog, five claim records, and
landing-page links. Those artifacts over-promoted an external compilation of
results and, in one case, incorrectly attached the lab's independent AutoRound
MTP5 result to a different external GPTQ claim. They were removed.

The older one-B70 GPTQ/MTP contribution remains in
[`community/sergiiob-qwen38-27b-vllm-xpu/`](../community/sergiiob-qwen38-27b-vllm-xpu/STATUS.md)
as an archival contribution with local validation. That is the appropriate
place for attribution. Its checkpoint failed the lab's no-loss quality gate,
its published MTP patch was redundant for the tested artifact, and it is not
the recipe behind the lab's two-B70 AutoRound lane.

## Lab Qwen lineage

The repository records the work that produced the performance:

- Qwen3.6 Q8 began at `15.550257 tok/s` on one B70 in the August optimization
  campaign.
- The lab's Qwen3.6 AutoRound, XPU kernel, runtime, graph, sampler, and MTP work
  created the stack later transferred to Qwen3.8.
- The first Qwen3.8 AutoRound observation was `91.925538 tok/s` on 2026-08-18.
- The honest margin-free Qwen3.8 MTP5 research anchor is `101.170 tok/s` on two
  B70s. It is not promoted because the three arms agree on only 21--22 of 25
  token arrays.
- Historical `100.497` and `101.922 tok/s` rows are invalid for promotion: an
  output-changing greedy margin was enabled in both candidate and baseline.

The `15.55 -> 101.17` endpoints use different checkpoints, quantization, and
GPU counts. They document the lab program's progression, not a like-for-like
percentage speedup. The current evidence and recipe status are in the
[`Qwen3.8 model board`](../README.md#qwen38-27b-model-board) and
[`AutoRound repro/status`](../repro/qwen38-27b-autoround-int4-b70/README.md).

## What remains from the source review

The Kydo/MLX review is retained separately under
[`community/field-reports/kydo/`](../community/field-reports/kydo/mlxfast-qwen38-27b-mlx-challenge/README.md).
It contains methodology and cross-platform hypotheses, not a B70 result or an
adopted patch. Any idea from it must earn a lab patch, controlled A/B, quality
gate, and in-repo recipe before it can affect a public result.

The cookbook review mentioned configuration hypotheses such as a larger
scheduler token budget, adaptive draft depth, and concurrency cache behavior.
None was implemented or shown to improve this lab's lane, so they are not
carried forward as endorsed optimization work. If a concrete novel patch is
later supplied, preserve it in this repository, pin its exact source identity,
measure its marginal effect, and credit that patch at the point of use.
