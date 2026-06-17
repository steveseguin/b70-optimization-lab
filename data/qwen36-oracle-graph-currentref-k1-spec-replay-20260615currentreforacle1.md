# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-graph-currentref-20260615a-spec.jsonl`
- rows: `30`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 20 | 20 | 20 | 0 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000001-0-b2c2291b` | 10 | 10 | 9 | 1 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 6 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 9 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 12 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 15 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 16 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 17 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 18 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 19 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 20 | 2 | 1 | 0 | 0 | 2 | 2 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
