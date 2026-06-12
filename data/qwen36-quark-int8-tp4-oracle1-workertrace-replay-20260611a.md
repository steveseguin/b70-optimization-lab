# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-quark-int8-tp4-oracle1-workertrace-spec-trace-20260611a.jsonl`
- rows: `15`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | follow-up mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| `cmpl-84f7445f48f11315-0-b01312e5` | 8 | 8 | 7 | 1 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 |
| `cmpl-a036bf49c31e1bd7-0-910cd43a` | 7 | 7 | 7 | 0 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-84f7445f48f11315-0-b01312e5` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-84f7445f48f11315-0-b01312e5` | 9 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-84f7445f48f11315-0-b01312e5` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-84f7445f48f11315-0-b01312e5` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-84f7445f48f11315-0-b01312e5` | 12 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-84f7445f48f11315-0-b01312e5` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-84f7445f48f11315-0-b01312e5` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-84f7445f48f11315-0-b01312e5` | 15 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-a036bf49c31e1bd7-0-910cd43a` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a036bf49c31e1bd7-0-910cd43a` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a036bf49c31e1bd7-0-910cd43a` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a036bf49c31e1bd7-0-910cd43a` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a036bf49c31e1bd7-0-910cd43a` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a036bf49c31e1bd7-0-910cd43a` | 6 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a036bf49c31e1bd7-0-910cd43a` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
