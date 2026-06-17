# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-oracle-k1-unsupp-microscope-static-20260615-spec.jsonl`
- rows: `23`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 16 | 16 | 16 | 0 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-oraclek1micro-000000-0-939d98c1` | 7 | 7 | 7 | 0 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 9 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 12 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 15 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 16 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 17 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 18 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 19 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 20 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 21 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 22 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000001-0-bdedbdcd` | 23 | 2 | 1 | 0 | 0 | 1 | 1 |
| `cmpl-oraclek1micro-000000-0-939d98c1` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000000-0-939d98c1` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000000-0-939d98c1` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-oraclek1micro-000000-0-939d98c1` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
