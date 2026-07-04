# Qwen27 Spec Verify Trace Summary

- verify trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-verifytrace-20260704T070717Z/verify-trace.jsonl`
- result JSON: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-verifytrace-20260704T070717Z-20260704T070717Z.json`
- classification: `diagnostic_only`; not a headline throughput claim
- trace rows: `563`
- skipped zero-draft warmup rows: `2`
- verifier steps: `561`
- draft tokens: `1683`
- prefix-accepted tokens: `1007`
- prefix acceptance fraction: `0.5983363042186571`
- mean target-verified tokens per step: `2.7950089126559714`
- mean output tokens per verifier step: `2.7950089126559714`
- full-accept rate: `0.40641711229946526`
- accepted histogram: `{0: 113, 1: 117, 2: 103, 3: 228}`
- per-position target-top1 match: `{'0': 0.7985739750445633, '1': 0.7183600713012478, '2': 0.6149732620320856}`

## Paired Strict Result

- median tok/s 1-100 after TTFT: `64.8999288973447`
- p10 tok/s 1-100 after TTFT: `57.15735989632373`
- mean tok/s 1-100 after TTFT: `63.71935288222712`
- median TTFT ms: `609.6218960592523`
- final gate: `{'cached_tokens': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 'cached_tokens_all_zero': True, 'chunk_count_matches_completion_tokens_all': False, 'chunk_count_matches_completion_tokens_note': 'Informational only: llama.cpp usage may count an EOS/final token that is not emitted as a text delta. Promotion requires enough streamed text deltas to measure the first metric window.', 'chunk_counts': [45, 48, 52, 42, 46, 47, 45, 45, 46, 46, 54, 48], 'completion_tokens_at_least_metric_window': True, 'metric_chunk_events_at_least_window': False, 'metric_name': 'median_tok_s_1_100_after_ttft', 'metric_token_id_events_at_least_window': True, 'metric_tokens': 100, 'passed': True, 'prompts_unique': True, 'required_policy': 'fixed realistic prompt suite; each prompt once; cached_tokens=0 every row; no repeated/warmed prompt averaging; metric is median tokens 1-100 after TTFT', 'return_token_ids_requested': True, 'stream_token_id_counts': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128], 'token_timing_source': 'openai_stream_token_ids_chunk_timestamp'}`

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
