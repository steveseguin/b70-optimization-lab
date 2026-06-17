# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-oracle1-paired-freshgraph-20260615g5-spec-trace.jsonl`
- rows: `14`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-b96876a2f0994db7-0-a6a5a8f1` | 9 | 9 | 8 | 1 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-9fe9fa7abd170bce-0-93fc9484` | 5 | 5 | 5 | 0 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-b96876a2f0994db7-0-a6a5a8f1` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b96876a2f0994db7-0-a6a5a8f1` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b96876a2f0994db7-0-a6a5a8f1` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b96876a2f0994db7-0-a6a5a8f1` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b96876a2f0994db7-0-a6a5a8f1` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b96876a2f0994db7-0-a6a5a8f1` | 6 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b96876a2f0994db7-0-a6a5a8f1` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b96876a2f0994db7-0-a6a5a8f1` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b96876a2f0994db7-0-a6a5a8f1` | 9 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-9fe9fa7abd170bce-0-93fc9484` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9fe9fa7abd170bce-0-93fc9484` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9fe9fa7abd170bce-0-93fc9484` | 12 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9fe9fa7abd170bce-0-93fc9484` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9fe9fa7abd170bce-0-93fc9484` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
