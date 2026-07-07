# 2026-07-07: Current-recipe strict top-k64 branch envelope

## Classification

Diagnostic only. No endpoint throughput claim, no quality claim, and no
LocalMaxxing submission.

## Objective

The earlier branch/regenerate feasibility model used an older BF16-scale
top-k64 diagnostic trace and normalized to the prior `67.519 tok/s` row. Before
spending source work on branch/regenerate, this run refreshed the envelope on
the current quality-gated recipe and the fixed strict Qwen realistic suite.

Question: can MTP3 branch/regenerate plausibly crack `100 tok/s` on the current
`68.236` recipe if the first rejected target token is selected from draft top-k
and the dependent suffix is regenerated perfectly?

## Run Identity

Raw run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-current-recipe-strict-topk64-branch-envelope-20260707T092955Z
```

Recipe:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`, revision
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- one B70, TP1, vLLM/XPU;
- MTP3, `PIECEWISE` graph, `max_cudagraph_capture_size=8`;
- ReplaySSM exact GDN state path, commit-in-forward, PyTorch slot-management
  fallback;
- target LM-head INT8 with BF16 scales;
- draft LM-head INT4 with BF16 scales;
- fixed Qwen realistic suite, each prompt once, `cached_tokens=0`,
  `return_token_ids=true`.

Diagnostic env:

```text
VLLM_XPU_DRAFT_TOPK_TRACE_FILE=<run>/draft-topk.jsonl
VLLM_XPU_DRAFT_TOPK_TRACE_K=64
VLLM_XPU_DRAFT_TOPK_TRACE_MAX_LINES=10000
VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_FILE=<run>/verify-trace.jsonl
VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_MAX_LINES=10000
```

Trace overhead slowed measured throughput to about `59.39 tok/s`, so the speed
row is not meaningful. The run did pass the strict freshness mechanics:
`cached_tokens=0` on all prompts, `realistic_final_gate.passed=true`.

## Artifacts

Raw:

```text
<run>/draft-topk.jsonl
<run>/verify-trace.jsonl
<run>/summary.json
```

Tracked summaries:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-current-recipe-strict-topk64-branch-envelope-20260707.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-current-recipe-strict-topk64-branch-envelope-20260707.md
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-current-recipe-strict-topk64-draft-join-20260707.json
```

Analyzer update:

```text
scripts/model-qwen27-branch-regenerate-feasibility.py
```

The analyzer interpretation now references the supplied trace and supplied
baseline instead of stale BF16-scale trace wording.

## Trace Shape

- aligned verifier steps: `2134`;
- accepted-prefix histogram: `0=435, 1=477, 2=415, 3=807`;
- current target tokens/step: `2.746954076850984`;
- full accept rate: `0.3781630740393627`;
- normalized baseline: `68.23626314761921 tok/s`;
- inferred step cost: `40.256513914139006 ms/step`.

Top-k join quality:

- exact group matches: `2134`;
- fallback matches: `0`;
- first-choice match rate: `1.0`.

Per-position target-in-top64 rate:

- position 0: `0.9985941893158388`;
- position 1: `0.9868791002811621`;
- position 2: `0.9770384254920338`.

This confirms the target token is almost always in the draft distribution, but
rank availability alone is not enough because Qwen MTP is sequential: changing
an early token invalidates later draft rows.

## Branch/Regenerate Envelope

Optimistic legal model: when the first rejected target token is inside draft
top-k, select it and regenerate the remaining suffix perfectly.

| cutoff | first-reject in top-k | optimistic target tokens/step | no-extra-cost tok/s | extra budget for 100 tok/s |
| ---: | ---: | ---: | ---: | ---: |
| 2 | `0.4076865109269028` | `3.2830365510777884` | `81.55292726240538` | `-7.426 ms` |
| 4 | `0.6548605877920121` | `3.6035613870665415` | `89.5149886736936` | `-4.221 ms` |
| 8 | `0.7920120572720422` | `3.7685098406747892` | `93.61242378593549` | `-2.571 ms` |
| 16 | `0.8952524491333835` | `3.8894095595126523` | `96.61565747615823` | `-1.362 ms` |
| 32 | `0.9397136397889977` | `3.9390815370196814` | `97.84954418609472` | `-0.866 ms` |
| 64 | `0.9668425018839487` | `3.9681349578256793` | `98.57125150700095` | `-0.575 ms` |

At the current step cost, `100 tok/s` requires `4.0256513914139` target tokens
per verifier step. MTP3 can emit at most `4` target-verified tokens/step
(`3` draft + `1` bonus), so MTP3 branch/regenerate cannot reach `100 tok/s`
even with perfect suffix regeneration and zero overhead.

## Decision

Close MTP3-only branch/regenerate as a `>100 tok/s` path. It remains useful as
infrastructure and could maybe improve the high-90s if step cost is reduced,
but it is not the primary optimization lane.

The next credible routes are:

1. reduce verifier-step cost by at least several milliseconds, ideally
   `>12 ms/step` if accepted depth stays near `2.75`; or
2. move to deeper verified speculation with a stronger drafter while keeping
   exact target verification and graph-safe GDN/DeltaNet state handling.

Do not spend large source-work time on MTP3 branch plumbing until one of those
two prerequisites changes the envelope.
