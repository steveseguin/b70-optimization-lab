# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle-ngram1-c1capture-adraftonly-20260615adraft1.jsonl`
- rows: `112`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 57 | 57 | 32 | 25 | 0 | `repetitive_kernel_notes (scheduler_prefix)` | 0 | 0 | 0 | 0 |
| `cmpl-ngram-adraft-20260615adraft1-000000-0-92c5194f` | 55 | 55 | 11 | 44 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 56 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 57 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 58 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 59 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 60 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 61 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 62 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 63 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 64 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 65 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 66 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 67 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 68 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 69 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 70 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 71 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 72 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 73 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 74 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-ngram-adraft-20260615adraft1-000001-0-a703cd12` | 75 | 2 | 0 | 1 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
