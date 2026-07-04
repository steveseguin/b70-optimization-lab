# Qwen27 Spec Verify Trace Summary

- verify trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-recordstack-verifytrace4gpu-gpu1-20260704T110712Z/verify-trace.jsonl`
- result JSON: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-recordstack-verifytrace4gpu-gpu1-20260704T110712Z-20260704T110712Z.json`
- classification: `diagnostic_only`; not a headline throughput claim
- trace rows: `564`
- skipped zero-draft warmup rows: `2`
- verifier steps: `562`
- draft tokens: `1686`
- prefix-accepted tokens: `1006`
- prefix acceptance fraction: `0.5966785290628707`
- mean target-verified tokens per step: `2.790035587188612`
- mean output tokens per verifier step: `2.790035587188612`
- full-accept rate: `0.40569395017793597`
- accepted histogram: `{0: 115, 1: 116, 2: 103, 3: 228}`
- per-position target-top1 match: `{'0': 0.7953736654804271, '1': 0.7188612099644128, '2': 0.6138790035587188}`

## Paired Strict Result

- median tok/s 1-100 after TTFT: `63.89308930597479`
- p10 tok/s 1-100 after TTFT: `56.17076834846764`
- mean tok/s 1-100 after TTFT: `62.54640915710834`
- median TTFT ms: `621.7613404151052`
- final gate: `{'cached_tokens': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 'cached_tokens_all_zero': True, 'chunk_count_matches_completion_tokens_all': False, 'chunk_count_matches_completion_tokens_note': 'Informational only: llama.cpp usage may count an EOS/final token that is not emitted as a text delta. Promotion requires enough streamed text deltas to measure the first metric window.', 'chunk_counts': [45, 48, 52, 43, 46, 47, 45, 45, 46, 46, 54, 48], 'completion_tokens_at_least_metric_window': True, 'metric_chunk_events_at_least_window': False, 'metric_name': 'median_tok_s_1_100_after_ttft', 'metric_token_id_events_at_least_window': True, 'metric_tokens': 100, 'passed': True, 'prompts_unique': True, 'required_policy': 'fixed realistic prompt suite; each prompt once; cached_tokens=0 every row; no repeated/warmed prompt averaging; metric is median tokens 1-100 after TTFT', 'return_token_ids_requested': True, 'stream_token_id_counts': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128], 'token_timing_source': 'openai_stream_token_ids_chunk_timestamp'}`

## Per-Prompt Trace Attribution

| prompt | steps | accepted/draft | mean target tokens/step | full accept | tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| incident-retrospective | 55 | 101/165 | 2.8363636363636364 | 0.38181818181818183 | 71.04540978612962 |
| code-review | 48 | 83/144 | 2.729166666666667 | 0.3541666666666667 | 58.88109884922701 |
| customer-email | 51 | 80/153 | 2.568627450980392 | 0.27450980392156865 | 55.86962051504993 |
| sql-debugging | 43 | 93/129 | 3.1627906976744184 | 0.5581395348837209 | 65.59210613202582 |
| release-plan | 45 | 78/135 | 2.7333333333333334 | 0.35555555555555557 | 64.11357922851987 |
| benchmark-analysis | 47 | 85/141 | 2.8085106382978724 | 0.46808510638297873 | 62.20331093542617 |
| architecture-tradeoff | 44 | 88/132 | 3.0 | 0.45454545454545453 | 67.77018439259824 |
| bug-report-synthesis | 45 | 88/135 | 2.9555555555555557 | 0.4888888888888889 | 65.65739725748293 |
| technical-guide | 44 | 78/132 | 2.7727272727272725 | 0.4090909090909091 | 63.79080253970796 |
| risk-register | 47 | 84/141 | 2.7872340425531914 | 0.40425531914893614 | 60.54832216812361 |
| performance-hypotheses | 54 | 80/162 | 2.4814814814814814 | 0.35185185185185186 | 51.08970200876735 |
| decision-memo | 39 | 68/117 | 2.7435897435897436 | 0.41025641025641024 | 63.99537607224162 |

## First Reject Examples

```json
[
  {
    "line_no": 3,
    "stage": "dense",
    "position": 2,
    "draft_token_id": 3746,
    "target_argmax_token_id": 10082,
    "output_token_ids": [
      37947,
      1653,
      10082
    ]
  },
  {
    "line_no": 8,
    "stage": "dense",
    "position": 0,
    "draft_token_id": 1851,
    "target_argmax_token_id": 37947,
    "output_token_ids": [
      37947
    ]
  },
  {
    "line_no": 9,
    "stage": "dense",
    "position": 2,
    "draft_token_id": 25,
    "target_argmax_token_id": 64700,
    "output_token_ids": [
      1653,
      2937,
      64700
    ]
  },
  {
    "line_no": 11,
    "stage": "dense",
    "position": 1,
    "draft_token_id": 19,
    "target_argmax_token_id": 18,
    "output_token_ids": [
      17,
      18
    ]
  },
  {
    "line_no": 14,
    "stage": "dense",
    "position": 0,
    "draft_token_id": 1851,
    "target_argmax_token_id": 63380,
    "output_token_ids": [
      63380
    ]
  },
  {
    "line_no": 15,
    "stage": "dense",
    "position": 1,
    "draft_token_id": 220,
    "target_argmax_token_id": 387,
    "output_token_ids": [
      64700,
      387
    ]
  },
  {
    "line_no": 16,
    "stage": "dense",
    "position": 2,
    "draft_token_id": 1460,
    "target_argmax_token_id": 40621,
    "output_token_ids": [
      16,
      318,
      40621
    ]
  },
  {
    "line_no": 18,
    "stage": "dense",
    "position": 2,
    "draft_token_id": 18,
    "target_argmax_token_id": 19,
    "output_token_ids": [
      64700,
      220,
      19
    ]
  }
]
```

## Interpretation

- The trace is emitted inside the verifier sampler, so `draft_token_ids` are real worker-side proposals rather than scheduler placeholders.
- Use this to decide whether drafter calibration can improve accepted tokens per verifier step.
- Any speed claim still requires the strict cold realistic suite with `cached_tokens=0`.
