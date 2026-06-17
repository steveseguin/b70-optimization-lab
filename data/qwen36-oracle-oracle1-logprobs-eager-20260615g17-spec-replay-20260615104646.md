# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-oracle1-logprobs-eager-20260615g17-spec-trace.jsonl`
- rows: `31`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 16 | 16 | 16 | 0 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-a5dd1236f8cd7ebd-0-ad3b7bd3` | 15 | 15 | 15 | 0 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 6 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 9 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 12 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 15 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 16 | 2 | 1 | 0 | 0 | 1 | 1 |
| `cmpl-a5dd1236f8cd7ebd-0-ad3b7bd3` | 17 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a5dd1236f8cd7ebd-0-ad3b7bd3` | 18 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a5dd1236f8cd7ebd-0-ad3b7bd3` | 19 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a5dd1236f8cd7ebd-0-ad3b7bd3` | 20 | 2 | 1 | 0 | 0 | 2 | 2 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
