# Qwen3.6 COW Parent-State Trace Summary

- Trace: `data/qwen36-quark-int8-tp4-accepted-graph-cowtrace-prodroot-parent-trace-20260612l.jsonl`
- Rows: `192`
- Malformed rows: `0`

| Stage | Rows | Spec rows | KV changed rows | num_computed delta rows | output delta rows | spec_len delta rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| after_output_commit | 64 | 0 | 0 | 0 | 64 | 0 |
| after_update_after_schedule | 64 | 0 | 0 | 0 | 0 | 0 |
| before_update_after_schedule | 64 | 0 | 0 | 0 | 0 | 0 |

## Schedule Transitions

Pairwise delta from `before_update_after_schedule` to `after_update_after_schedule` for the same parent request.

- Transitions: `64`
- Spec transitions: `0`
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
| `num_output_placeholders` | 64 | 1 |
| `spec_len` | 0 | 0 |

## Examples

### after_output_commit

```json
{
  "delta": {
    "num_computed_tokens": 0,
    "num_output_placeholders": -1,
    "num_output_tokens": 1,
    "num_tokens": 1,
    "num_tokens_with_spec": 1,
    "spec_len": 0
  },
  "num_scheduled_tokens": 502,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0
}
```

```json
{
  "delta": {
    "num_computed_tokens": 0,
    "num_output_placeholders": -1,
    "num_output_tokens": 1,
    "num_tokens": 1,
    "num_tokens_with_spec": 1,
    "spec_len": 0
  },
  "num_scheduled_tokens": 1,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0
}
```

```json
{
  "delta": {
    "num_computed_tokens": 0,
    "num_output_placeholders": -1,
    "num_output_tokens": 1,
    "num_tokens": 1,
    "num_tokens_with_spec": 1,
    "spec_len": 0
  },
  "num_scheduled_tokens": 1,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0
}
```

```json
{
  "delta": {
    "num_computed_tokens": 0,
    "num_output_placeholders": -1,
    "num_output_tokens": 1,
    "num_tokens": 1,
    "num_tokens_with_spec": 1,
    "spec_len": 0
  },
  "num_scheduled_tokens": 1,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0
}
```

```json
{
  "delta": {
    "num_computed_tokens": 0,
    "num_output_placeholders": -1,
    "num_output_tokens": 1,
    "num_tokens": 1,
    "num_tokens_with_spec": 1,
    "spec_len": 0
  },
  "num_scheduled_tokens": 1,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0
}
```

## Schedule Transition Examples

```json
{
  "delta": {
    "kv_block_lengths_after": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_before": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 502,
    "num_output_placeholders": 1,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 502,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0,
  "scheduled_spec_token_ids": []
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_before": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 1,
    "num_output_placeholders": 1,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 1,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0,
  "scheduled_spec_token_ids": []
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_before": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 1,
    "num_output_placeholders": 1,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 1,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0,
  "scheduled_spec_token_ids": []
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_before": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 1,
    "num_output_placeholders": 1,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 1,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0,
  "scheduled_spec_token_ids": []
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_before": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 1,
    "num_output_placeholders": 1,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 1,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0,
  "scheduled_spec_token_ids": []
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_before": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 1,
    "num_output_placeholders": 1,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 1,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0,
  "scheduled_spec_token_ids": []
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_before": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 1,
    "num_output_placeholders": 1,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 1,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0,
  "scheduled_spec_token_ids": []
}
```

```json
{
  "delta": {
    "kv_block_lengths_after": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_before": [
      1,
      1,
      1,
      1
    ],
    "kv_block_lengths_changed": false,
    "kv_last_block_ids_changed": false,
    "num_computed_tokens": 1,
    "num_output_placeholders": 1,
    "num_output_tokens": 0,
    "num_tokens": 0,
    "num_tokens_with_spec": 0,
    "spec_len": 0
  },
  "num_scheduled_tokens": 1,
  "req_id": "cmpl-b2f379ea4672f32c-0-8fedba6e",
  "scheduled_spec_len": 0,
  "scheduled_spec_token_ids": []
}
```
