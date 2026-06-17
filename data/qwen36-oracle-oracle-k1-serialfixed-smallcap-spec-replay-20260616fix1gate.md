# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-spec.jsonl`
- rows: `32`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 16 | 16 | 14 | 2 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000001-0-9f62fab5` | 16 | 16 | 16 | 0 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 6 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 9 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 11 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 12 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 15 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 16 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000001-0-9f62fab5` | 17 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000001-0-9f62fab5` | 18 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000001-0-9f62fab5` | 19 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000001-0-9f62fab5` | 20 | 2 | 1 | 0 | 0 | 2 | 2 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
