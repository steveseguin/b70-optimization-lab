# Qwen27 Spec Verify Trace Summary

- verify trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-drafttopk-calib-20260704T143725Z/verify-trace.jsonl`
- result JSON: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-drafttopk-calib-20260704T143725Z-20260704T143725Z.json`
- classification: `diagnostic_only`; not a headline throughput claim
- trace rows: `1149`
- skipped zero-draft warmup rows: `2`
- verifier steps: `1147`
- draft tokens: `3441`
- prefix-accepted tokens: `1964`
- prefix acceptance fraction: `0.5707643126997965`
- mean target-verified tokens per step: `2.71229293809939`
- mean output tokens per verifier step: `2.71229293809939`
- full-accept rate: `0.36006974716652135`
- accepted histogram: `{0: 227, 1: 289, 2: 218, 3: 413}`
- per-position target-top1 match: `{'0': 0.8020924149956408, '1': 0.6765475152571927, '2': 0.5937227550130776}`

## Paired Strict Result

- median tok/s 1-100 after TTFT: `56.67099790175303`
- p10 tok/s 1-100 after TTFT: `51.04490084471975`
- mean tok/s 1-100 after TTFT: `56.56681688038654`
- median TTFT ms: `639.4904374610633`
- final gate: `{'cached_tokens': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 'cached_tokens_all_zero': True, 'chunk_count_matches_completion_tokens_all': False, 'chunk_count_matches_completion_tokens_note': 'Informational only: llama.cpp usage may count an EOS/final token that is not emitted as a text delta. Promotion requires enough streamed text deltas to measure the first metric window.', 'chunk_counts': [46, 46, 51, 44, 52, 48, 50, 50, 43, 47, 46, 57, 49, 43, 49, 49, 49, 48, 51, 53, 47, 46, 44, 47], 'completion_tokens_at_least_metric_window': True, 'metric_chunk_events_at_least_window': False, 'metric_name': 'median_tok_s_1_100_after_ttft', 'metric_token_id_events_at_least_window': True, 'metric_tokens': 100, 'passed': True, 'prompts_unique': True, 'required_policy': 'fixed realistic prompt suite; each prompt once; cached_tokens=0 every row; no repeated/warmed prompt averaging; metric is median tokens 1-100 after TTFT', 'return_token_ids_requested': True, 'stream_token_id_counts': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128], 'token_timing_source': 'openai_stream_token_ids_chunk_timestamp'}`

## Per-Prompt Trace Attribution

| prompt | steps | accepted/draft | mean target tokens/step | full accept | tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| ops-runbook | 54 | 99/162 | 2.833333333333333 | 0.42592592592592593 | 55.946566195146715 |
| api-design-review | 49 | 94/147 | 2.9183673469387754 | 0.4489795918367347 | 56.835012995452466 |
| incident-questions | 48 | 71/144 | 2.479166666666667 | 0.22916666666666666 | 53.702026821124996 |
| security-brief | 45 | 86/135 | 2.9111111111111114 | 0.4222222222222222 | 63.866113404325844 |
| indexing-plan | 51 | 85/153 | 2.666666666666667 | 0.37254901960784315 | 46.361935847969804 |
| benchmark-policy | 48 | 74/144 | 2.541666666666667 | 0.2916666666666667 | 55.26122951708548 |
| migration-memo | 49 | 72/147 | 2.4693877551020407 | 0.2653061224489796 | 58.440243299794545 |
| quality-gate-design | 48 | 92/144 | 2.916666666666667 | 0.4375 | 56.78733390270022 |
| cache-bug | 43 | 86/129 | 3.0 | 0.4883720930232558 | 63.698417400205514 |
| capacity-plan | 46 | 73/138 | 2.5869565217391304 | 0.2391304347826087 | 57.84084861125781 |
| code-path-audit | 45 | 86/135 | 2.9111111111111114 | 0.4 | 63.87865765161491 |
| customer-root-cause | 56 | 70/168 | 2.25 | 0.16071428571428573 | 47.50378466114864 |
| router-design | 49 | 90/147 | 2.836734693877551 | 0.4489795918367347 | 52.46800307097182 |
| perf-experiment-template | 44 | 88/132 | 3.0 | 0.4772727272727273 | 61.40430137715765 |
| runtime-risk-register | 48 | 81/144 | 2.6875 | 0.3333333333333333 | 56.55466190080585 |
| release-retro | 49 | 74/147 | 2.510204081632653 | 0.2857142857142857 | 54.92643614549047 |
| support-playbook | 47 | 82/141 | 2.74468085106383 | 0.3404255319148936 | 52.439868422599204 |
| architecture-summary | 48 | 80/144 | 2.666666666666667 | 0.4166666666666667 | 60.16350902689853 |
| scheduler-debug | 51 | 76/153 | 2.4901960784313726 | 0.27450980392156865 | 51.13276092238773 |
| kernel-change-review | 52 | 82/156 | 2.5769230769230766 | 0.3076923076923077 | 51.00724652571919 |
| handoff-note | 47 | 85/141 | 2.8085106382978724 | 0.3829787234042553 | 61.96583248184213 |
| long-context-plan | 46 | 83/138 | 2.8043478260869565 | 0.34782608695652173 | 58.26347833764724 |
| variance-method | 45 | 90/135 | 3.0 | 0.4888888888888889 | 62.03316634486819 |
| optimization-stop-rule | 39 | 65/117 | 2.666666666666667 | 0.4358974358974359 | 55.12217026506211 |

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
