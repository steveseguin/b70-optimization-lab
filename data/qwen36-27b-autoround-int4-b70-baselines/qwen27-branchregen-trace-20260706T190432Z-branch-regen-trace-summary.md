# Qwen27 Branch/Regenerate Trace Summary

Classification: diagnostic only, no endpoint mutation, no headline result.

Trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-branchregen-trace-20260706T190432Z/branch-regen-cow-trace.jsonl`

| metric | value |
| --- | ---: |
| `scheduled_rows` | 220 |
| `partial_reject_rows` | 134 |
| `partial_reject_rate` | 0.609091 |
| `full_accept_rows` | 86 |
| `full_accept_rate` | 0.390909 |
| `mean_raw_visible_tokens` | 2.672727 |
| `mean_accepted_draft_prefix` | 1.672727 |
| `mean_scheduled_spec_len` | 3 |
| `branchable_remaining_draft_rows` | 292 |

Histograms:

```json
{
  "hist_draft_prefix_count": {
    "0": 56,
    "1": 46,
    "2": 32,
    "3": 86
  },
  "hist_first_reject_index": {
    "0": 56,
    "1": 46,
    "2": 32
  },
  "hist_raw_visible_count": {
    "1": 56,
    "2": 46,
    "3": 32,
    "4": 86
  },
  "hist_scheduled_spec_len": {
    "3": 220
  }
}
```

Interpretation: normal MTP verifier rows expose accepted draft prefix as `max(raw_visible_count - 1, 0)` clamped to scheduled spec length; the target-owned replacement/bonus tail is deliberately excluded.
