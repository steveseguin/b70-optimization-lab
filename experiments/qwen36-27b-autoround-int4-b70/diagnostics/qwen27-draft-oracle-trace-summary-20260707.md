# Qwen27 Draft Oracle Trace Summary

Classification: diagnostic only, no headline throughput result.

Trace: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-draft-oracle-trace-20260707T111040Z/draft-oracle-cow-trace.jsonl`

This asks whether the target-owned bonus/replacement token appears later in the same proposed draft row. A hit is only an upper-bound branch/tail signal; it is not valid to commit without exact target verification and GDN/DeltaNet state replay.

| metric | value |
| --- | ---: |
| `paired_rows` | 2143 |
| `partial_reject_rows` | 1344 |
| `partial_reject_rate` | 0.627158 |
| `full_accept_rows` | 799 |
| `full_accept_rate` | 0.372842 |
| `mean_raw_visible_tokens` | 2.737751 |
| `mean_accepted_drafts` | 1.737751 |
| `max_k` | 3 |
| `magic_all_full_visible_tokens` | 4 |
| `magic_all_full_same_cost_multiplier` | 1.461053 |
| `prefix_mismatch_rows` | 0 |
| `bonus_in_unaccepted_tail_rows` | 42 |
| `bonus_in_unaccepted_tail_rate_over_partial` | 0.031250 |
| `bonus_in_unaccepted_tail_rate_over_all` | 0.019599 |

Histograms:

```json
{
  "hist_accepted_drafts": {
    "0": 439,
    "1": 483,
    "2": 422,
    "3": 799
  },
  "hist_raw_visible_tokens": {
    "1": 439,
    "2": 483,
    "3": 422,
    "4": 799
  }
}
```

Counters:

```json
{
  "proposals": 2156,
  "scheduled_verify_rows": 2143,
  "unpaired_proposals_remaining": 13
}
```
