# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-serialgdn-cow-paired-20260615g10-spec-trace.jsonl`
- rows: `6`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-975f60d8a448fb1c-0-a44ae2d9` | 4 | 4 | 3 | 1 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-a415a4dec2b1cf7f-0-83233257` | 2 | 2 | 1 | 1 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-975f60d8a448fb1c-0-a44ae2d9` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-975f60d8a448fb1c-0-a44ae2d9` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-975f60d8a448fb1c-0-a44ae2d9` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-975f60d8a448fb1c-0-a44ae2d9` | 4 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-a415a4dec2b1cf7f-0-83233257` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-a415a4dec2b1cf7f-0-83233257` | 6 | 2 | 0 | 1 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
