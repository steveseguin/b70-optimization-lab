# Qwen3.6 Spec Trace Replay

- trace: `/tmp/qwen36-oracle1-short-graph-spec-trace-20260611a.jsonl`
- rows: `15`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | follow-up mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| `cmpl-96c535d8fe063261-0-9b4f19dd` | 8 | 8 | 7 | 1 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 |
| `cmpl-a606b4e303f78310-0-842ceef3` | 7 | 7 | 7 | 0 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-96c535d8fe063261-0-9b4f19dd` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-96c535d8fe063261-0-9b4f19dd` | 9 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-96c535d8fe063261-0-9b4f19dd` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-96c535d8fe063261-0-9b4f19dd` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-96c535d8fe063261-0-9b4f19dd` | 12 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-96c535d8fe063261-0-9b4f19dd` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-96c535d8fe063261-0-9b4f19dd` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-96c535d8fe063261-0-9b4f19dd` | 15 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-a606b4e303f78310-0-842ceef3` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a606b4e303f78310-0-842ceef3` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a606b4e303f78310-0-842ceef3` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a606b4e303f78310-0-842ceef3` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a606b4e303f78310-0-842ceef3` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a606b4e303f78310-0-842ceef3` | 6 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a606b4e303f78310-0-842ceef3` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
