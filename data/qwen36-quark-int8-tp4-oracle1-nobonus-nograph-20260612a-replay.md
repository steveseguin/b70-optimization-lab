# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-quark-int8-tp4-oracle1-nobonus-nograph-20260612a-spec-trace.jsonl`
- rows: `16`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | follow-up mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| `cmpl-90583939dcf68be9-0-8b7d15a2` | 9 | 9 | 4 | 5 | 4 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 |
| `cmpl-bcef8a4a7367bcb8-0-84e2b9a7` | 7 | 7 | 3 | 4 | 3 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-90583939dcf68be9-0-8b7d15a2` | 1 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-90583939dcf68be9-0-8b7d15a2` | 2 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-90583939dcf68be9-0-8b7d15a2` | 3 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-90583939dcf68be9-0-8b7d15a2` | 4 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-90583939dcf68be9-0-8b7d15a2` | 5 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-90583939dcf68be9-0-8b7d15a2` | 6 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-90583939dcf68be9-0-8b7d15a2` | 7 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-90583939dcf68be9-0-8b7d15a2` | 8 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-90583939dcf68be9-0-8b7d15a2` | 9 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-bcef8a4a7367bcb8-0-84e2b9a7` | 10 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-bcef8a4a7367bcb8-0-84e2b9a7` | 11 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-bcef8a4a7367bcb8-0-84e2b9a7` | 12 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-bcef8a4a7367bcb8-0-84e2b9a7` | 13 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-bcef8a4a7367bcb8-0-84e2b9a7` | 14 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-bcef8a4a7367bcb8-0-84e2b9a7` | 15 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-bcef8a4a7367bcb8-0-84e2b9a7` | 16 | 2 | 0 | 1 | -1 | 1 | 1 |
