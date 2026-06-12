# Qwen3.6 COW Parent-State Trace Summary

- Trace: `data/qwen36-quark-int8-tp4-oracle1-nobonus-nograph-20260612a-parent-trace.jsonl`
- Rows: `192`
- Malformed rows: `0`

| Stage | Rows | Spec rows | KV changed rows | num_computed delta rows | output delta rows | spec_len delta rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| after_output_commit | 64 | 16 | 0 | 0 | 64 | 0 |
| after_update_after_schedule | 64 | 16 | 0 | 0 | 0 | 0 |
| before_update_after_schedule | 64 | 16 | 0 | 0 | 0 | 0 |

## Schedule Transitions

Pairwise delta from `before_update_after_schedule` to `after_update_after_schedule` for the same parent request.

- Transitions: `64`
- Spec transitions: `16`
- Unmatched before rows: `0`
- Unmatched after rows: `0`
- KV block length changed rows: `0`
- KV last-block changed rows: `0`

| Field | Nonzero rows | Max abs delta |
| --- | ---: | ---: |
| `num_output_tokens` | 0 | 0 |
| `num_tokens` | 0 | 0 |
| `num_tokens_with_spec` | 0 | 0 |
| `num_computed_tokens` | 64 | 502 |
| `num_output_placeholders` | 0 | 0 |
| `spec_len` | 0 | 0 |

## Examples

### after_output_commit

```json
{
  "delta": {
    "num_computed_tokens": 0,
    "num_output_placeholders": 0,
    "num_output_tokens": 1,
    "num_tokens": 1,
    "num_tokens_with_spec": 1,
    "spec_len": 0
  },
  "num_scheduled_tokens": 502,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 0
}
```

```json
{
  "delta": {
    "num_computed_tokens": 0,
    "num_output_placeholders": 0,
    "num_output_tokens": 1,
    "num_tokens": 1,
    "num_tokens_with_spec": 1,
    "spec_len": 0
  },
  "num_scheduled_tokens": 2,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 1
}
```

```json
{
  "delta": {
    "num_computed_tokens": 0,
    "num_output_placeholders": 0,
    "num_output_tokens": 1,
    "num_tokens": 1,
    "num_tokens_with_spec": 1,
    "spec_len": 0
  },
  "num_scheduled_tokens": 2,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 1
}
```

```json
{
  "delta": {
    "num_computed_tokens": 0,
    "num_output_placeholders": 0,
    "num_output_tokens": 1,
    "num_tokens": 1,
    "num_tokens_with_spec": 1,
    "spec_len": 0
  },
  "num_scheduled_tokens": 2,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 1
}
```

```json
{
  "delta": {
    "num_computed_tokens": 0,
    "num_output_placeholders": 0,
    "num_output_tokens": 1,
    "num_tokens": 1,
    "num_tokens_with_spec": 1,
    "spec_len": 0
  },
  "num_scheduled_tokens": 2,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 1
}
```

## Schedule Transition Examples

```json
{
  "delta": {
    "kv_block_lengths_after": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_before": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 502,
    "num_output_placeholders": 0,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 502,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 0,
  "scheduled_spec_token_ids": []
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_before": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 2,
    "num_output_placeholders": 0,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 2,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 1,
  "scheduled_spec_token_ids": [
    440
  ]
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_before": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 2,
    "num_output_placeholders": 0,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 2,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 1,
  "scheduled_spec_token_ids": [
    47193
  ]
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_before": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 2,
    "num_output_placeholders": 0,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 2,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 1,
  "scheduled_spec_token_ids": [
    47193
  ]
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_before": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 2,
    "num_output_placeholders": 0,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 2,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 1,
  "scheduled_spec_token_ids": [
    8129
  ]
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_before": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 2,
    "num_output_placeholders": 0,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 2,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 1,
  "scheduled_spec_token_ids": [
    8129
  ]
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_before": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 2,
    "num_output_placeholders": 0,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 2,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 1,
  "scheduled_spec_token_ids": [
    24985
  ]
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_before": [
      2,
      2,
      2,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 2,
    "num_output_placeholders": 0,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 2,
  "req_id": "cmpl-90583939dcf68be9-0-8b7d15a2",
  "scheduled_spec_len": 1,
  "scheduled_spec_token_ids": [
    24985
  ]
}
```
