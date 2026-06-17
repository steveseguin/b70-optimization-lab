# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-microscope-currentref-20260615microscope1-spec.jsonl`
- rows: `30`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 20 | 20 | 20 | 0 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000001-0-963081b3` | 10 | 10 | 9 | 1 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 6 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 9 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 12 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 15 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 16 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 17 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 18 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 19 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-microscope-currentref-20260615microscope1-000000-0-9d0802bc` | 20 | 2 | 1 | 0 | 0 | 2 | 2 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
