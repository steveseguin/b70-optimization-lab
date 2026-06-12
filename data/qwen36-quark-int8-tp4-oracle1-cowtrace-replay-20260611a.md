# Qwen3.6 Spec Trace Replay

- trace: `/tmp/qwen36-oracle1-cowtrace-20260611a-spec-trace.jsonl`
- rows: `15`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | follow-up mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| `cmpl-b02534e0916481a8-0-a9332139` | 8 | 8 | 7 | 1 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 |
| `cmpl-81172901c0bd6189-0-899f3038` | 7 | 7 | 7 | 0 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-b02534e0916481a8-0-a9332139` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b02534e0916481a8-0-a9332139` | 9 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b02534e0916481a8-0-a9332139` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b02534e0916481a8-0-a9332139` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b02534e0916481a8-0-a9332139` | 12 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b02534e0916481a8-0-a9332139` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b02534e0916481a8-0-a9332139` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b02534e0916481a8-0-a9332139` | 15 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-81172901c0bd6189-0-899f3038` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-81172901c0bd6189-0-899f3038` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-81172901c0bd6189-0-899f3038` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-81172901c0bd6189-0-899f3038` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-81172901c0bd6189-0-899f3038` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-81172901c0bd6189-0-899f3038` | 6 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-81172901c0bd6189-0-899f3038` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
