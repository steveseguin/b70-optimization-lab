# Qwen27 Spec Verify Trace Summary

- verify trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-recordstack-verifytrace4gpu-gpu2-20260704T110712Z/verify-trace.jsonl`
- result JSON: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-recordstack-verifytrace4gpu-gpu2-20260704T110712Z-20260704T110712Z.json`
- classification: `diagnostic_only`; not a headline throughput claim
- trace rows: `565`
- skipped zero-draft warmup rows: `2`
- verifier steps: `563`
- draft tokens: `1689`
- prefix-accepted tokens: `1005`
- prefix acceptance fraction: `0.5950266429840142`
- mean target-verified tokens per step: `2.785079928952043`
- mean output tokens per verifier step: `2.7850799289520425`
- full-accept rate: `0.40319715808170514`
- accepted histogram: `{0: 117, 1: 114, 2: 105, 3: 227}`
- per-position target-top1 match: `{'0': 0.7921847246891652, '1': 0.7246891651865008, '2': 0.6127886323268206}`

## Paired Strict Result

- median tok/s 1-100 after TTFT: `62.633029082926726`
- p10 tok/s 1-100 after TTFT: `51.98288321615073`
- mean tok/s 1-100 after TTFT: `59.03213097576745`
- median TTFT ms: `623.3284724876285`
- final gate: `{'cached_tokens': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 'cached_tokens_all_zero': True, 'chunk_count_matches_completion_tokens_all': False, 'chunk_count_matches_completion_tokens_note': 'Informational only: llama.cpp usage may count an EOS/final token that is not emitted as a text delta. Promotion requires enough streamed text deltas to measure the first metric window.', 'chunk_counts': [45, 48, 52, 43, 47, 47, 45, 45, 46, 46, 54, 48], 'completion_tokens_at_least_metric_window': True, 'metric_chunk_events_at_least_window': False, 'metric_name': 'median_tok_s_1_100_after_ttft', 'metric_token_id_events_at_least_window': True, 'metric_tokens': 100, 'passed': True, 'prompts_unique': True, 'required_policy': 'fixed realistic prompt suite; each prompt once; cached_tokens=0 every row; no repeated/warmed prompt averaging; metric is median tokens 1-100 after TTFT', 'return_token_ids_requested': True, 'stream_token_id_counts': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128], 'token_timing_source': 'openai_stream_token_ids_chunk_timestamp'}`

## Per-Prompt Trace Attribution

| prompt | steps | accepted/draft | mean target tokens/step | full accept | tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| incident-retrospective | 55 | 101/165 | 2.8363636363636364 | 0.38181818181818183 | 25.0226471100132 |
| code-review | 48 | 83/144 | 2.729166666666667 | 0.3541666666666667 | 59.446964487355785 |
| customer-email | 51 | 81/153 | 2.5882352941176467 | 0.29411764705882354 | 56.53185376300215 |
| sql-debugging | 43 | 92/129 | 3.13953488372093 | 0.5116279069767442 | 66.28782701401882 |
| release-plan | 47 | 77/141 | 2.6382978723404253 | 0.3404255319148936 | 62.60395668041644 |
| benchmark-analysis | 46 | 85/138 | 2.8478260869565215 | 0.4782608695652174 | 62.66210148543701 |
| architecture-tradeoff | 44 | 88/132 | 3.0 | 0.45454545454545453 | 68.24422068558485 |
| bug-report-synthesis | 45 | 88/135 | 2.9555555555555557 | 0.4888888888888889 | 66.19286523551227 |
| technical-guide | 44 | 78/132 | 2.7727272727272725 | 0.4090909090909091 | 64.3359199269361 |
| risk-register | 47 | 84/141 | 2.7872340425531914 | 0.40425531914893614 | 60.81386944167047 |
| performance-hypotheses | 54 | 80/162 | 2.4814814814814814 | 0.35185185185185186 | 51.47744204427835 |
| decision-memo | 39 | 68/117 | 2.7435897435897436 | 0.41025641025641024 | 64.76590383498403 |

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
