# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-graph-safe-20260615a-spec.jsonl`
- rows: `16`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000000-0-ac51e8c3` | 9 | 9 | 8 | 1 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000001-0-aba6a0f3` | 7 | 7 | 7 | 0 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000000-0-ac51e8c3` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000000-0-ac51e8c3` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000000-0-ac51e8c3` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000000-0-ac51e8c3` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000000-0-ac51e8c3` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000000-0-ac51e8c3` | 6 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000000-0-ac51e8c3` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000000-0-ac51e8c3` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000000-0-ac51e8c3` | 9 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000001-0-aba6a0f3` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000001-0-aba6a0f3` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000001-0-aba6a0f3` | 12 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000001-0-aba6a0f3` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000001-0-aba6a0f3` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000001-0-aba6a0f3` | 15 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-safe-20260615a-000001-0-aba6a0f3` | 16 | 2 | 1 | 0 | 0 | 2 | 2 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
