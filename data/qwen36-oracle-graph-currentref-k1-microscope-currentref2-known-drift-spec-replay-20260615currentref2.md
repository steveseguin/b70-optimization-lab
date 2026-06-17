# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-microscope-currentref2-20260615-spec.jsonl`
- rows: `7`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-microscope-currentref2-20260615-000001-0-9656a86b` | 4 | 20 | 15 | 5 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-qwen36-oracle-k1-microscope-currentref2-20260615-000000-0-aee1f4ce` | 3 | 15 | 11 | 4 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-microscope-currentref2-20260615-000001-0-9656a86b` | 4 | 6 | 5 | 0 | 0 | 6 | 6 |
| `cmpl-qwen36-oracle-k1-microscope-currentref2-20260615-000001-0-9656a86b` | 5 | 6 | 5 | 0 | 0 | 6 | 6 |
| `cmpl-qwen36-oracle-k1-microscope-currentref2-20260615-000001-0-9656a86b` | 6 | 6 | 5 | 0 | 0 | 6 | 6 |
| `cmpl-qwen36-oracle-k1-microscope-currentref2-20260615-000001-0-9656a86b` | 7 | 6 | 0 | 5 | -5 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-microscope-currentref2-20260615-000000-0-aee1f4ce` | 1 | 6 | 5 | 0 | 0 | 6 | 6 |
| `cmpl-qwen36-oracle-k1-microscope-currentref2-20260615-000000-0-aee1f4ce` | 2 | 6 | 5 | 0 | 0 | 6 | 6 |
| `cmpl-qwen36-oracle-k1-microscope-currentref2-20260615-000000-0-aee1f4ce` | 3 | 6 | 1 | 4 | -4 | 2 | 2 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
