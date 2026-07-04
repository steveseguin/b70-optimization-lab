# Qwen27 Spec Verify Trace Summary

- verify trace: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-calibration-verifytrace-20260704A-verify-trace.jsonl`
- result JSON: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-calibration-verifytrace-20260704A-20260704T071847Z.json`
- classification: `diagnostic_only`; not a headline throughput claim
- trace rows: `1159`
- skipped zero-draft warmup rows: `2`
- verifier steps: `1157`
- draft tokens: `3471`
- prefix-accepted tokens: `1951`
- prefix acceptance fraction: `0.5620858542206857`
- mean target-verified tokens per step: `2.686257562662057`
- mean output tokens per verifier step: `2.686257562662057`
- full-accept rate: `0.3500432152117545`
- accepted histogram: `{0: 237, 1: 294, 2: 221, 3: 405}`
- per-position target-top1 match: `{'0': 0.7951598962834918, '1': 0.6698357821953328, '2': 0.5859982713915298}`

## Paired Strict Result

- median tok/s 1-100 after TTFT: `63.11820703948129`
- p10 tok/s 1-100 after TTFT: `57.15554850685666`
- mean tok/s 1-100 after TTFT: `63.14942796082557`
- median TTFT ms: `618.4663685271516`
- final gate: `{'cached_tokens': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 'cached_tokens_all_zero': True, 'chunk_count_matches_completion_tokens_all': False, 'chunk_count_matches_completion_tokens_note': 'Informational only: llama.cpp usage may count an EOS/final token that is not emitted as a text delta. Promotion requires enough streamed text deltas to measure the first metric window.', 'chunk_counts': [50, 46, 50, 44, 52, 48, 51, 50, 43, 47, 46, 57, 49, 43, 49, 49, 49, 53, 51, 53, 47, 46, 44, 48], 'completion_tokens_at_least_metric_window': True, 'metric_chunk_events_at_least_window': False, 'metric_name': 'median_tok_s_1_100_after_ttft', 'metric_token_id_events_at_least_window': True, 'metric_tokens': 100, 'passed': True, 'prompts_unique': True, 'required_policy': 'fixed realistic prompt suite; each prompt once; cached_tokens=0 every row; no repeated/warmed prompt averaging; metric is median tokens 1-100 after TTFT', 'return_token_ids_requested': True, 'stream_token_id_counts': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128], 'token_timing_source': 'openai_stream_token_ids_chunk_timestamp'}`

## Per-Prompt Trace Attribution

| prompt | steps | accepted/draft | mean target tokens/step | full accept | tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| ops-runbook | 60 | 99/180 | 2.65 | 0.3333333333333333 | 66.41973951530282 |
| api-design-review | 48 | 92/144 | 2.916666666666667 | 0.4375 | 63.27848282915364 |
| incident-questions | 49 | 72/147 | 2.4693877551020407 | 0.24489795918367346 | 59.86680687619556 |
| security-brief | 44 | 84/132 | 2.909090909090909 | 0.4318181818181818 | 71.10689935788334 |
| indexing-plan | 51 | 85/153 | 2.666666666666667 | 0.37254901960784315 | 59.87393117827335 |
| benchmark-policy | 48 | 76/144 | 2.583333333333333 | 0.3125 | 61.49224495664764 |
| migration-memo | 50 | 71/150 | 2.42 | 0.26 | 63.17252279752687 |
| quality-gate-design | 48 | 90/144 | 2.875 | 0.4166666666666667 | 63.15583103885594 |
| cache-bug | 43 | 88/129 | 3.046511627906977 | 0.5116279069767442 | 70.93908979163776 |
| capacity-plan | 46 | 73/138 | 2.5869565217391304 | 0.2391304347826087 | 64.87788573991656 |
| code-path-audit | 45 | 86/135 | 2.9111111111111114 | 0.4 | 70.94803154141576 |
| customer-root-cause | 56 | 68/168 | 2.2142857142857144 | 0.14285714285714285 | 52.824410509152294 |
| router-design | 49 | 92/147 | 2.8775510204081636 | 0.4489795918367347 | 58.23035175069689 |
| perf-experiment-template | 44 | 86/132 | 2.9545454545454546 | 0.45454545454545453 | 68.7821181186747 |
| runtime-risk-register | 48 | 82/144 | 2.708333333333333 | 0.3333333333333333 | 63.08058304010664 |
| release-retro | 48 | 72/144 | 2.5 | 0.2916666666666667 | 61.379835566847326 |
| support-playbook | 48 | 84/144 | 2.75 | 0.3333333333333333 | 58.22311345507875 |
| architecture-summary | 52 | 70/156 | 2.3461538461538463 | 0.3076923076923077 | 61.3242148841964 |
| scheduler-debug | 51 | 76/153 | 2.4901960784313726 | 0.27450980392156865 | 56.65215533894939 |
| kernel-change-review | 53 | 84/159 | 2.5849056603773586 | 0.3018867924528302 | 56.69802067190433 |
| handoff-note | 47 | 84/141 | 2.7872340425531914 | 0.3829787234042553 | 68.67600704315024 |
| long-context-plan | 46 | 85/138 | 2.8478260869565215 | 0.3695652173913043 | 64.74885382741388 |
| variance-method | 44 | 87/132 | 2.9772727272727275 | 0.4772727272727273 | 68.5927858386064 |
| optimization-stop-rule | 39 | 65/117 | 2.666666666666667 | 0.4358974358974359 | 61.242355392227346 |

## First Reject Examples

```json
[
  {
    "line_no": 7,
    "stage": "dense",
    "position": 2,
    "draft_token_id": 1510,
    "target_argmax_token_id": 79995,
    "output_token_ids": [
      2937,
      64700,
      79995
    ]
  },
  {
    "line_no": 9,
    "stage": "dense",
    "position": 2,
    "draft_token_id": 12,
    "target_argmax_token_id": 198,
    "output_token_ids": [
      15,
      16,
      198
    ]
  },
  {
    "line_no": 13,
    "stage": "dense",
    "position": 1,
    "draft_token_id": 13384,
    "target_argmax_token_id": 5237,
    "output_token_ids": [
      498,
      5237
    ]
  },
  {
    "line_no": 15,
    "stage": "dense",
    "position": 0,
    "draft_token_id": 82105,
    "target_argmax_token_id": 13405,
    "output_token_ids": [
      13405
    ]
  },
  {
    "line_no": 16,
    "stage": "dense",
    "position": 1,
    "draft_token_id": 498,
    "target_argmax_token_id": 9698,
    "output_token_ids": [
      64700,
      9698
    ]
  },
  {
    "line_no": 17,
    "stage": "dense",
    "position": 1,
    "draft_token_id": 28905,
    "target_argmax_token_id": 7659,
    "output_token_ids": [
      16107,
      7659
    ]
  },
  {
    "line_no": 18,
    "stage": "dense",
    "position": 2,
    "draft_token_id": 82105,
    "target_argmax_token_id": 37332,
    "output_token_ids": [
      198,
      332,
      37332
    ]
  },
  {
    "line_no": 19,
    "stage": "dense",
    "position": 1,
    "draft_token_id": 4962,
    "target_argmax_token_id": 71855,
    "output_token_ids": [
      64700,
      71855
    ]
  }
]
```

## Interpretation

- The trace is emitted inside the verifier sampler, so `draft_token_ids` are real worker-side proposals rather than scheduler placeholders.
- Use this to decide whether drafter calibration can improve accepted tokens per verifier step.
- Any speed claim still requires the strict cold realistic suite with `cached_tokens=0`.
