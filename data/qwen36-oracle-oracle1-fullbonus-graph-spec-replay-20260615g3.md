# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-oracle1-fullbonus-graph-20260615g3-spec-trace.jsonl`
- rows: `16`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-88d3d0d524cd03d0-0-a153089a` | 9 | 9 | 8 | 1 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-ac1b34d038cd3a2e-0-984e9884` | 7 | 7 | 7 | 0 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-88d3d0d524cd03d0-0-a153089a` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-88d3d0d524cd03d0-0-a153089a` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-88d3d0d524cd03d0-0-a153089a` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-88d3d0d524cd03d0-0-a153089a` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-88d3d0d524cd03d0-0-a153089a` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-88d3d0d524cd03d0-0-a153089a` | 6 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-88d3d0d524cd03d0-0-a153089a` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-88d3d0d524cd03d0-0-a153089a` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-88d3d0d524cd03d0-0-a153089a` | 9 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-ac1b34d038cd3a2e-0-984e9884` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ac1b34d038cd3a2e-0-984e9884` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ac1b34d038cd3a2e-0-984e9884` | 12 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ac1b34d038cd3a2e-0-984e9884` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ac1b34d038cd3a2e-0-984e9884` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ac1b34d038cd3a2e-0-984e9884` | 15 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ac1b34d038cd3a2e-0-984e9884` | 16 | 2 | 1 | 0 | 0 | 2 | 2 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
