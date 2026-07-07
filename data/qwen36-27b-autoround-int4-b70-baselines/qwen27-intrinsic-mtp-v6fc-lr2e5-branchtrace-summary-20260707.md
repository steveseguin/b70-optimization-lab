# Qwen27 Branch/Regenerate Trace Summary

Classification: diagnostic only, no endpoint mutation, no headline result.

Trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-intrinsic-mtp-v6fc-lr2e5-branchtrace-cow-trace.jsonl`

| metric | value |
| --- | ---: |
| `scheduled_rows` | 220 |
| `partial_reject_rows` | 153 |
| `partial_reject_rate` | 0.695455 |
| `full_accept_rows` | 67 |
| `full_accept_rate` | 0.304545 |
| `mean_raw_visible_tokens` | 2.577273 |
| `mean_accepted_draft_prefix` | 1.577273 |
| `mean_scheduled_spec_len` | 3 |
| `branchable_remaining_draft_rows` | 313 |

Histograms:

```json
{
  "hist_draft_prefix_count": {
    "0": 50,
    "1": 60,
    "2": 43,
    "3": 67
  },
  "hist_first_reject_index": {
    "0": 50,
    "1": 60,
    "2": 43
  },
  "hist_raw_visible_count": {
    "1": 50,
    "2": 60,
    "3": 43,
    "4": 67
  },
  "hist_scheduled_spec_len": {
    "3": 220
  }
}
```

Interpretation: normal MTP verifier rows expose accepted draft prefix as `max(raw_visible_count - 1, 0)` clamped to scheduled spec length; the target-owned replacement/bonus tail is deliberately excluded.
