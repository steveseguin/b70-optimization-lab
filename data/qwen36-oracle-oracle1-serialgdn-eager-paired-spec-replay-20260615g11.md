# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-serialgdn-eager-paired-20260615g11-spec-trace.jsonl`
- rows: `16`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 12 | 12 | 10 | 2 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-b778328a79aacaf2-0-bc09d75b` | 4 | 4 | 3 | 1 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 6 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 9 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 12 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 15 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 16 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b778328a79aacaf2-0-bc09d75b` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b778328a79aacaf2-0-bc09d75b` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b778328a79aacaf2-0-bc09d75b` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-b778328a79aacaf2-0-bc09d75b` | 4 | 2 | 0 | 1 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
