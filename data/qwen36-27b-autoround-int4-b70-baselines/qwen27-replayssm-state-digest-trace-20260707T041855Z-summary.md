# Qwen27 ReplaySSM State Trace Summary

Classification: diagnostic only, no endpoint mutation, no headline result.

Trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-replayssm-state-digest-trace-20260707T041855Z-20260707T041855Z/gdn-replayssm-state-trace.jsonl`

| metric | value |
| --- | ---: |
| `record_count` | 80 |

Stage counts:

```json
{
  "replayssm_after_spec_decode": 20,
  "replayssm_after_stage_conv": 20,
  "replayssm_commit_pending_after": 20,
  "replayssm_commit_pending_before": 20
}
```

Cursor and pending histograms:

```json
{
  "accepted_token_value_counts": {
    "1": 189,
    "2": 9,
    "3": 9,
    "4": 53
  },
  "cache_base_value_counts": {
    "0": 25,
    "1": 4,
    "2": 4,
    "3": 12,
    "4": 7,
    "5": 4,
    "6": 4,
    "7": 12
  },
  "pending_len_value_counts": {
    "0": 6,
    "4": 66
  },
  "pending_value_counts": {
    "0": 38,
    "1": 34
  },
  "state_digest_record_counts": {
    "conv_pending": 80,
    "conv_state": 80,
    "d_cache": 80,
    "g_cache": 80,
    "k_cache": 80
  },
  "write_pos_value_counts": {
    "0": 10,
    "1": 4,
    "2": 12,
    "3": 12,
    "4": 34
  }
}
```

First records:

```json
[
  {
    "cache_base": [],
    "has_state_digest": true,
    "layer": "language_model.model.layers.0.linear_attn",
    "layer_idx": 0,
    "num_accepted_tokens": [
      4,
      1,
      1,
      1
    ],
    "pending": [],
    "pending_len": [],
    "slots_sample": [],
    "stage": "replayssm_commit_pending_before",
    "write_pos": []
  },
  {
    "cache_base": [],
    "has_state_digest": true,
    "layer": "language_model.model.layers.0.linear_attn",
    "layer_idx": 0,
    "num_accepted_tokens": [
      4,
      1,
      1,
      1
    ],
    "pending": [],
    "pending_len": [],
    "slots_sample": [],
    "stage": "replayssm_commit_pending_after",
    "write_pos": []
  },
  {
    "cache_base": [],
    "has_state_digest": true,
    "layer": "language_model.model.layers.0.linear_attn",
    "layer_idx": 0,
    "num_accepted_tokens": [
      4,
      1,
      1,
      1
    ],
    "pending": [],
    "pending_len": [],
    "slots_sample": [],
    "stage": "replayssm_after_stage_conv",
    "write_pos": []
  },
  {
    "cache_base": [],
    "has_state_digest": true,
    "layer": "language_model.model.layers.0.linear_attn",
    "layer_idx": 0,
    "num_accepted_tokens": [
      4
    ],
    "pending": [],
    "pending_len": [],
    "slots_sample": [],
    "stage": "replayssm_after_spec_decode",
    "write_pos": []
  },
  {
    "cache_base": [],
    "has_state_digest": true,
    "layer": "language_model.model.layers.0.linear_attn",
    "layer_idx": 0,
    "num_accepted_tokens": [
      4,
      1,
      1,
      1
    ],
    "pending": [],
    "pending_len": [],
    "slots_sample": [],
    "stage": "replayssm_commit_pending_before",
    "write_pos": []
  },
  {
    "cache_base": [],
    "has_state_digest": true,
    "layer": "language_model.model.layers.0.linear_attn",
    "layer_idx": 0,
    "num_accepted_tokens": [
      4,
      1,
      1,
      1
    ],
    "pending": [],
    "pending_len": [],
    "slots_sample": [],
    "stage": "replayssm_commit_pending_after",
    "write_pos": []
  },
  {
    "cache_base": [],
    "has_state_digest": true,
    "layer": "language_model.model.layers.0.linear_attn",
    "layer_idx": 0,
    "num_accepted_tokens": [
      4,
      1,
      1,
      1
    ],
    "pending": [],
    "pending_len": [],
    "slots_sample": [],
    "stage": "replayssm_after_stage_conv",
    "write_pos": []
  },
  {
    "cache_base": [],
    "has_state_digest": true,
    "layer": "language_model.model.layers.0.linear_attn",
    "layer_idx": 0,
    "num_accepted_tokens": [
      4
    ],
    "pending": [],
    "pending_len": [],
    "slots_sample": [],
    "stage": "replayssm_after_spec_decode",
    "write_pos": []
  }
]
```

Diagnostic trace only. Stage/cursor coverage can show whether the ReplaySSM transaction points were observed; correctness still requires the existing GDN unit contracts and endpoint quality gate.
