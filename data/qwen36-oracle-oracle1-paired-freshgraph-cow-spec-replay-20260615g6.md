# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-paired-freshgraph-cow-20260615g6-spec-trace.jsonl`
- rows: `14`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-ab4fd2c4fcb669b9-0-9aca6577` | 9 | 9 | 8 | 1 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-a009d16fc2994c55-0-8343dbfe` | 5 | 5 | 5 | 0 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-ab4fd2c4fcb669b9-0-9aca6577` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab4fd2c4fcb669b9-0-9aca6577` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab4fd2c4fcb669b9-0-9aca6577` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab4fd2c4fcb669b9-0-9aca6577` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab4fd2c4fcb669b9-0-9aca6577` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab4fd2c4fcb669b9-0-9aca6577` | 6 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab4fd2c4fcb669b9-0-9aca6577` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab4fd2c4fcb669b9-0-9aca6577` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab4fd2c4fcb669b9-0-9aca6577` | 9 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-a009d16fc2994c55-0-8343dbfe` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a009d16fc2994c55-0-8343dbfe` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a009d16fc2994c55-0-8343dbfe` | 12 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a009d16fc2994c55-0-8343dbfe` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a009d16fc2994c55-0-8343dbfe` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
