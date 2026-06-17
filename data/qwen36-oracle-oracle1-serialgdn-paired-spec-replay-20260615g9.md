# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-serialgdn-paired-20260615g9-spec-trace.jsonl`
- rows: `6`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-ab2712b9992fdef2-0-abdc413e` | 4 | 4 | 3 | 1 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-9269fb496b17b8de-0-b9f4d0e4` | 2 | 2 | 1 | 1 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-ab2712b9992fdef2-0-abdc413e` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab2712b9992fdef2-0-abdc413e` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab2712b9992fdef2-0-abdc413e` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ab2712b9992fdef2-0-abdc413e` | 4 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-9269fb496b17b8de-0-b9f4d0e4` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-9269fb496b17b8de-0-b9f4d0e4` | 6 | 2 | 0 | 1 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
